"""Final temporal comparison: RF, Ridge, NB-GAM and EBM, grouped vs ungrouped.

High/low groups are defined from training-only target counts (top 20%). Models
predict counts, then predictions are mapped to the existing bounded risk score.
The low-group hurdle hybrid is included as a separate, fixed low-activity setup.
"""
from pathlib import Path
import argparse
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import jarque_bera, skew, kurtosis
from statsmodels.gam.api import BSplines, GLMGam
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from interpret.glassbox import ExplainableBoostingRegressor
from statsmodels.stats.diagnostic import het_breuschpagan

ROOT = Path.cwd()
if ROOT.name == "processing_datasets":
    ROOT = ROOT.parent
DATA_PATH = ROOT / "datasets" / "database_processed_h3_risk.csv"
OUT = ROOT / "datasets"
TARGETS = {"RISCO_CRIME": "CNT_CRIME_COUNT", "RISCO_FURTO": "FURTO_COUNT", "RISCO_ROUBO": "ROUBO_COUNT"}
FEATURES = {
    "RISCO_CRIME": ["crime_media_12m_log", "crime_razao_3_12", "crime_sazonal_12", "crime_pct_meses_12m", "crime_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_FURTO": ["furto_media_12m_log", "furto_razao_3_12", "furto_sazonal_12", "furto_pct_meses_12m", "furto_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_ROUBO": ["roubo_media_12m_log", "roubo_razao_3_12", "roubo_sazonal_12", "roubo_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
}
EXTRA = ["ewm3", "resid_lag1", "resid_mean3"]
FOLDS = [("2024-01-01", "2024-06-01"), ("2024-07-01", "2024-12-01"), ("2025-01-01", "2025-06-01")]
HIGH_SHARE = .20
RF_PARAMS = dict(n_estimators=250, max_depth=12, min_samples_leaf=5, max_features=.7,
                 bootstrap=True, max_samples=.8, n_jobs=-1, random_state=42)


def score_count(count, k):
    count = np.maximum(np.asarray(count, dtype=float), 0)
    return count / (count + k)


def rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def design(train, valid, features):
    a = train[features].replace([np.inf, -np.inf], np.nan)
    b = valid[features].replace([np.inf, -np.inf], np.nan)
    med = a.median().fillna(0)
    return a.fillna(med), b.fillna(med)


def history_table(data, count_col, k):
    h = data[["H3", "DATA", count_col]].copy()
    h["y"] = score_count(h[count_col], k)
    h["ewm3"] = h.groupby("H3", sort=False).y.transform(lambda s: s.shift().ewm(halflife=3, adjust=False, min_periods=1).mean())
    h["residual"] = h.y - h.ewm3
    h["resid_lag1"] = h.groupby("H3", sort=False).residual.shift()
    h["resid_mean3"] = h.groupby("H3", sort=False).residual.transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
    return h[["H3", "DATA", "y", "ewm3", "resid_lag1", "resid_mean3"]]


def fit_low_hurdle(train_low, valid_all, count_col, features, k):
    xtr, xva = design(train_low, valid_all, features)
    event = (train_low[count_col] > 0).astype(int)
    classifier = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=2000, random_state=42))
    classifier.fit(xtr, event)
    p_event = classifier.predict_proba(xva)[:, 1]
    positives = event.eq(1)
    pos_count = train_low.loc[positives, count_col].astype(float)
    mu, var = float(pos_count.mean()), float(pos_count.var())
    alpha = max((var - mu) / (mu * mu), .01) if mu > 0 else .01
    scaler = StandardScaler().fit(xtr)
    xp = sm.add_constant(scaler.transform(xtr.loc[positives]), has_constant="add")
    xv = sm.add_constant(scaler.transform(xva), has_constant="add")
    model = sm.GLM(pos_count.to_numpy(), xp, family=sm.families.NegativeBinomial(alpha=alpha)).fit(maxiter=100, disp=0)
    return p_event * np.maximum(model.predict(xv), 0)


def fit_count_model(name, train, valid, count_col, features):
    xtr, xva = design(train, valid, features)
    y = train[count_col].astype(float).to_numpy()
    if name == "RF":
        model = RandomForestRegressor(**RF_PARAMS).fit(xtr, y)
        return np.maximum(model.predict(xva), 0), model, None
    if name == "Ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.)).fit(xtr, y)
        return np.maximum(model.predict(xva), 0), model, None
    if name == "Ridge_log1p":
        y_log = np.log1p(y)
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.)).fit(xtr, y_log)
        residual_log = y_log - model.predict(xtr)
        smear = float(np.mean(np.exp(np.clip(residual_log, -30, 30))))
        pred_count = np.exp(np.clip(model.predict(xva), -30, 30)) * smear - 1
        return np.maximum(pred_count, 0), model, {"smearing": smear}
    if name == "EBM":
        model = ExplainableBoostingRegressor(
            feature_names=features, interactions=0, objective="poisson_deviance",
            max_rounds=900, early_stopping_rounds=0, outer_bags=1, validation_size=0,
            learning_rate=.03, max_leaves=2, min_samples_leaf=20, n_jobs=-1, random_state=42)
        model.fit(xtr, y)
        return np.maximum(model.predict(xva), 0), model, (xtr, xva)
    if name == "GAM":
        linear = [c for c in features if c in {"MES_SIN", "MES_COS", "SEM_DOMICILIOS"}]
        smooth = [c for c in features if c not in linear]
        scaler = StandardScaler().fit(xtr)
        ztr = pd.DataFrame(scaler.transform(xtr), columns=features, index=train.index)
        zva = pd.DataFrame(scaler.transform(xva), columns=features, index=valid.index)
        active = [c for c in smooth if ztr[c].nunique() > 1]
        smtr, smva = ztr[active].copy(), zva[active].copy()
        for col in active:
            lo, hi = float(smtr[col].min()), float(smtr[col].max())
            eps = max((hi - lo) * 1e-6, 1e-8)
            smtr[col] = smtr[col].clip(lo + eps, hi - eps)
            smva[col] = smva[col].clip(lo + eps, hi - eps)
        ex = sm.add_constant(ztr[linear], has_constant="add")
        ev = sm.add_constant(zva[linear], has_constant="add")
        mu, var = float(y.mean()), float(y.var())
        nb_alpha = max((var - mu) / (mu * mu), .01) if mu > 0 else .01
        smoother = BSplines(smtr, df=[4] * len(active), degree=[3] * len(active))
        gam = GLMGam(y, exog=ex, smoother=smoother,
                     family=sm.families.NegativeBinomial(alpha=nb_alpha), alpha=.1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = gam.fit(maxiter=150, method="pirls")
        pred = np.asarray(fitted.predict(exog=ev, exog_smooth=smva), dtype=float)
        return np.maximum(pred, 0), fitted, {"kind": "GAM", "linear": linear, "active": active,
                                             "smoother": smoother}
    raise ValueError(name)


def fit_residual_model(name, train, valid, features):
    """Fit a model to y - EWM3; this target is signed, so log1p is not valid."""
    xtr, xva = design(train, valid, features)
    y = (train.y - train.ewm3).astype(float).to_numpy()
    if name == "RF":
        model = RandomForestRegressor(**RF_PARAMS).fit(xtr, y)
        return model.predict(xva), model, {"kind": "RF"}
    if name == "Ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.)).fit(xtr, y)
        return model.predict(xva), model, {"kind": "Ridge"}
    if name == "EBM":
        model = ExplainableBoostingRegressor(
            feature_names=features, interactions=0, objective="rmse",
            max_rounds=900, early_stopping_rounds=0, outer_bags=1, validation_size=0,
            learning_rate=.03, max_leaves=2, min_samples_leaf=20, n_jobs=-1, random_state=42)
        model.fit(xtr, y)
        return model.predict(xva), model, {"kind": "EBM"}
    if name == "GAM":
        linear = [c for c in features if c in {"MES_SIN", "MES_COS", "SEM_DOMICILIOS"}]
        smooth = [c for c in features if c not in linear]
        scaler = StandardScaler().fit(xtr)
        ztr = pd.DataFrame(scaler.transform(xtr), columns=features, index=train.index)
        zva = pd.DataFrame(scaler.transform(xva), columns=features, index=valid.index)
        active = [c for c in smooth if ztr[c].nunique() > 1]
        smtr, smva = ztr[active].copy(), zva[active].copy()
        for col in active:
            lo, hi = float(smtr[col].min()), float(smtr[col].max())
            eps = max((hi - lo) * 1e-6, 1e-8)
            smtr[col] = smtr[col].clip(lo + eps, hi - eps)
            smva[col] = smva[col].clip(lo + eps, hi - eps)
        ex = sm.add_constant(ztr[linear], has_constant="add")
        ev = sm.add_constant(zva[linear], has_constant="add")
        smoother = BSplines(smtr, df=[4] * len(active), degree=[3] * len(active))
        gam = GLMGam(y, exog=ex, smoother=smoother,
                     family=sm.families.Gaussian(), alpha=.1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = gam.fit(maxiter=150, method="pirls")
        pred = np.asarray(fitted.predict(exog=ev, exog_smooth=smva), dtype=float)
        train_pred = np.asarray(fitted.predict(exog=ex, exog_smooth=smtr), dtype=float)
        return pred, fitted, {"kind": "GAM", "linear": linear, "active": active,
                              "smoother": smoother, "train_prediction": train_pred}
    raise ValueError(name)


def model_importance(name, model, features, metadata=None):
    """Return native, model-specific feature importance (methods are not cross-model comparable)."""
    metadata = metadata or {}
    if name == "RF":
        values = np.asarray(model.feature_importances_, dtype=float)
        method = "redução de impureza da floresta"
        signed = [np.nan] * len(features)
    elif name in {"Ridge", "Ridge_log1p"}:
        coef = np.asarray(model[-1].coef_, dtype=float).reshape(-1)
        values, signed = np.abs(coef), coef
        method = "coeficiente Ridge padronizado (módulo)"
    elif name == "EBM":
        term_map = dict(zip(model.term_names_, model.term_importances()))
        values = np.array([float(term_map.get(f, 0.0)) for f in features])
        signed = [np.nan] * len(features)
        method = "importância dos termos EBM"
    elif name == "GAM":
        params = np.asarray(model.params, dtype=float)
        linear = metadata.get("linear", [])
        active = metadata.get("active", [])
        smoothers = metadata.get("smoother")
        values_by_feature = {f: 0.0 for f in features}
        signed_by_feature = {f: np.nan for f in features}
        # The linear coefficients are standardized. Each smooth term is summarized
        # by the L1 magnitude of its spline-basis coefficients.
        offset = 1  # intercept added by add_constant
        for i, feat in enumerate(linear):
            if offset + i < len(params):
                signed_by_feature[feat] = float(params[offset + i])
                values_by_feature[feat] = abs(float(params[offset + i]))
        offset += len(linear)
        # BSplines drops one basis column per feature when include_intercept=False.
        widths = [int(df) - 1 for df in getattr(smoothers, "dfs", [4] * len(active))]
        for feat, width in zip(active, widths):
            block = params[offset:offset + int(width)]
            values_by_feature[feat] = float(np.abs(block).sum())
            offset += int(width)
        values = np.array([values_by_feature[f] for f in features])
        signed = [signed_by_feature[f] for f in features]
        method = "coeficientes lineares / magnitude dos splines GAM"
    else:
        return []
    return [
        {"feature": feat, "importancia": float(val), "coeficiente_padronizado": float(coef) if np.isfinite(coef) else np.nan,
         "metodo_importancia": method}
        for feat, val, coef in zip(features, values, signed)
    ]


def ridge_diagnostics(target, fold, model_name, scope, train, valid, features, model,
                      train_target, valid_target, vif_cache, diagnostic_rows, vif_rows,
                      shape_rows=None):
    """Collect predictive-regression diagnostics for one scaled Ridge fit."""
    xtr, xva = design(train, valid, features)
    scaler = model[0]
    ztr = scaler.transform(xtr)
    fit = model.predict(xtr)
    resid = np.asarray(train_target, dtype=float) - fit
    val_error = np.asarray(valid_target, dtype=float) - model.predict(xva)
    jb = jarque_bera(resid)
    try:
        bp_lm, bp_p, _, _ = het_breuschpagan(resid, sm.add_constant(ztr, has_constant="add"))
    except Exception:
        bp_lm = bp_p = np.nan
    diagnostic_rows.append({
        "target": target, "fold": fold, "modelo": model_name, "escopo": scope,
        "escala_resposta": ("correção do score de risco" if "_resid_" in model_name else
                            "log(1 + contagem)" if "log1p" in model_name else "contagem"),
        "n_treino": len(train), "media_residuo_treino": float(np.mean(resid)),
        "desvio_residuo_treino": float(np.std(resid, ddof=1)),
        "assimetria_residuo_treino": float(skew(resid, bias=False)),
        "curtose_excesso_residuo_treino": float(kurtosis(resid, fisher=True, bias=False)),
        "jarque_bera_stat": float(jb.statistic), "jarque_bera_p": float(jb.pvalue),
        "breusch_pagan_lm": float(bp_lm), "breusch_pagan_p": float(bp_p),
        "corr_abs_residuo_ajustado_treino": float(np.corrcoef(np.abs(resid), fit)[0, 1]),
        "media_erro_validacao": float(np.mean(val_error)),
        "sd_erro_validacao": float(np.std(val_error, ddof=1)),
        "frac_previsao_no_limite_0_1": np.nan,
    })
    if shape_rows is not None:
        bins = pd.qcut(pd.Series(fit), q=10, duplicates="drop")
        shape = pd.DataFrame({"faixa_ajustada": bins, "ajustado": fit, "residuo": resid}).groupby(
            "faixa_ajustada", observed=True).agg(
                ajustado_medio=("ajustado", "mean"), residuo_medio=("residuo", "mean"),
                sd_residuo=("residuo", "std"), n=("residuo", "size")).reset_index()
        for _, row in shape.iterrows():
            shape_rows.append({"target": target, "fold": fold, "modelo": model_name,
                               "escopo": scope, **row.to_dict()})
    cache_key = (target, fold, scope)
    if cache_key not in vif_cache:
        scales = np.nanstd(ztr, axis=0)
        active = np.flatnonzero(scales > 1e-10)
        values = [{"feature": feat, "VIF": np.nan} for feat in features]
        if len(active):
            corr = np.corrcoef(ztr[:, active], rowvar=False)
            inverse_corr = np.linalg.pinv(np.atleast_2d(corr))
            for j, idx in enumerate(active):
                values[idx]["VIF"] = float(inverse_corr[j, j])
        vif_cache[cache_key] = values
    for item in vif_cache[cache_key]:
        vif_rows.append({"target": target, "fold": fold, "modelo": model_name,
                         "escopo": scope, **item})


def split_model_name(name):
    if name in {"EWM3", "media_historica_fixa", "EWM3_alto_HurdleNB_baixo"}:
        return None, "baseline", False
    if "_resid_" in name:
        algorithm, strategy = name.split("_resid_", 1)
        return algorithm, strategy, True
    for suffix, strategy in [
        ("_grupos_mesmo_modelo", "grupos_mesmo_modelo"),
        ("_alto_HurdleNB_baixo", "alto_HurdleNB_baixo"),
        ("_global", "global"),
    ]:
        if name.endswith(suffix):
            return name[:-len(suffix)], strategy, False
    raise ValueError(f"Não reconheço a configuração do modelo: {name}")


def evaluate_reserved_test():
    """Fit each CV winner on 2023-Jun/2025, then evaluate Jul/2025-Jun/2026."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Não encontrei a base de risco: {DATA_PATH}")
    summary_path = OUT / "final_model_comparison_groups_h3_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError("Execute a comparação temporal antes do teste reservado.")
    cv = pd.read_csv(summary_path)
    if "avaliacao" in cv:
        cv = cv[cv.avaliacao.eq("validacao_temporal")]
    data = pd.read_csv(DATA_PATH, parse_dates=["DATA"], low_memory=False)
    data = data.sort_values(["H3", "DATA"]).reset_index(drop=True)
    data = data[data.DATA.between("2022-01-01", "2026-06-01")].copy()
    train0 = data[data.DATA.between("2023-01-01", "2025-06-01")].copy()
    test0 = data[data.DATA.between("2025-07-01", "2026-06-01")].copy()
    if train0.empty or test0.empty:
        raise ValueError("O conjunto de treino ou o período reservado está vazio.")
    if test0.DATA.nunique() != 12:
        raise ValueError(f"O teste reservado deveria conter 12 meses; encontrei {test0.DATA.nunique()}.")

    baseline_names = {"EWM3", "media_historica_fixa", "EWM3_alto_HurdleNB_baixo"}
    selected_rows = []
    prediction_rows = []
    final_importance_rows = []
    final_gam_diagnostics = []
    test_autocorrelation_rows = []
    test_shape_rows = []

    for target, count_col in TARGETS.items():
        candidates = cv[(cv.target == target) & (~cv.modelo.isin(baseline_names))]
        if candidates.empty:
            raise ValueError(f"Não encontrei modelos candidatos para {target} na validação temporal.")
        selected_model = str(candidates.sort_values("RMSE_risco_medio").iloc[0].modelo)
        algorithm, strategy, residual_target = split_model_name(selected_model)

        positives = train0.loc[train0[count_col] > 0, count_col]
        k = float(positives.quantile(.90)) if len(positives) else 1.0
        history = history_table(data, count_col, k)
        train = train0.merge(history, on=["H3", "DATA"], how="left", validate="one_to_one")
        test = test0.merge(history, on=["H3", "DATA"], how="left", validate="one_to_one")
        train = train.dropna(subset=["ewm3"]).copy()
        features = FEATURES[target] + EXTRA

        totals = train.groupby("H3")[count_col].sum().sort_values(ascending=False, kind="stable")
        high_n = max(1, int(np.ceil(HIGH_SHARE * len(totals))))
        high_set = set(totals.head(high_n).index)
        train["grupo"] = np.where(train.H3.isin(high_set), "alto", "baixo")
        test["grupo"] = np.where(test.H3.isin(high_set), "alto", "baixo")
        high_train, low_train = train[train.grupo.eq("alto")].copy(), train[train.grupo.eq("baixo")].copy()
        high_test, low_test = test[test.grupo.eq("alto")].copy(), test[test.grupo.eq("baixo")].copy()
        high_mask = test.grupo.eq("alto").to_numpy()

        cell_mean = train.groupby("H3").y.mean()
        fixed = test.H3.map(cell_mean).fillna(float(train.y.mean())).to_numpy()
        ewm = test.ewm3.fillna(pd.Series(fixed, index=test.index)).to_numpy()
        truth = test.y.to_numpy()
        predictions = {"EWM3": ewm, "media_historica_fixa": fixed}
        fitted_scopes = []

        if algorithm is None:
            if selected_model == "EWM3_alto_HurdleNB_baixo":
                low_hurdle = fit_low_hurdle(low_train, test, count_col, FEATURES[target], k)
                pred = score_count(low_hurdle, k)
                pred[high_mask] = ewm[high_mask]
                predictions[selected_model] = pred
            else:
                predictions[selected_model] = ewm if selected_model == "EWM3" else fixed
        elif strategy == "global":
            if residual_target:
                correction, model, metadata = fit_residual_model(algorithm, train, test, features)
                predictions[selected_model] = np.clip(ewm + correction, 0, 1)
                fitted_scopes.append(("global", model, metadata))
            else:
                pred_count, model, metadata = fit_count_model(algorithm, train, test, count_col, features)
                predictions[selected_model] = score_count(pred_count, k)
                fitted_scopes.append(("global", model, metadata))
        elif strategy == "grupos_mesmo_modelo":
            pred = np.empty(len(test), dtype=float)
            if residual_target:
                corr_hi, mod_hi, meta_hi = fit_residual_model(algorithm, high_train, high_test, features)
                corr_lo, mod_lo, meta_lo = fit_residual_model(algorithm, low_train, low_test, features)
                pred[high_mask] = np.clip(ewm[high_mask] + corr_hi, 0, 1)
                pred[~high_mask] = np.clip(ewm[~high_mask] + corr_lo, 0, 1)
            else:
                cnt_hi, mod_hi, meta_hi = fit_count_model(algorithm, high_train, high_test, count_col, features)
                cnt_lo, mod_lo, meta_lo = fit_count_model(algorithm, low_train, low_test, count_col, features)
                pred[high_mask] = score_count(cnt_hi, k)
                pred[~high_mask] = score_count(cnt_lo, k)
            predictions[selected_model] = pred
            fitted_scopes.extend([("alto", mod_hi, meta_hi), ("baixo", mod_lo, meta_lo)])
        elif strategy == "alto_HurdleNB_baixo":
            low_hurdle = fit_low_hurdle(low_train, test, count_col, FEATURES[target], k)
            pred = score_count(low_hurdle, k)
            if residual_target:
                correction, model, metadata = fit_residual_model(algorithm, high_train, high_test, features)
                pred[high_mask] = np.clip(ewm[high_mask] + correction, 0, 1)
            else:
                pred_count, model, metadata = fit_count_model(algorithm, high_train, high_test, count_col, features)
                pred[high_mask] = score_count(pred_count, k)
            predictions[selected_model] = pred
            fitted_scopes.append(("alto", model, metadata))
        else:
            raise ValueError(f"Estratégia não implementada para o teste reservado: {strategy}")

        if selected_model not in predictions:
            raise RuntimeError(f"Não gerei previsões para o modelo selecionado {selected_model}.")

        # Holdout metrics for both baselines and this target's selected model.
        for model_name in ["EWM3", "media_historica_fixa", selected_model]:
            pred = predictions[model_name]
            rmse_value = rmse(truth, pred)
            mae_value = float(mean_absolute_error(truth, pred))
            ewm_rmse, fixed_rmse = rmse(truth, ewm), rmse(truth, fixed)
            selected_rows.append({
                "target": target, "modelo": model_name, "folds": 1,
                "RMSE_risco_medio": rmse_value, "MAE_risco_medio": mae_value,
                "ganho_medio_vs_EWM3_pct": (ewm_rmse - rmse_value) / ewm_rmse * 100,
                "ganho_medio_vs_media_fixa_pct": (fixed_rmse - rmse_value) / fixed_rmse * 100,
                "folds_melhor_EWM3": int(rmse_value < ewm_rmse),
                "folds_melhor_media_fixa": int(rmse_value < fixed_rmse),
                "avaliacao": "teste_reservado", "n_teste": len(test),
                "H3_teste": test.H3.nunique(), "meses_teste": test.DATA.nunique(),
                "modelo_selecionado_validacao": selected_model,
            })

        selected_pred = predictions[selected_model]
        prediction_rows.append(pd.DataFrame({
            "fold": 4, "particao": "teste_reservado", "target": target,
            "H3": test.H3.to_numpy(), "DATA": test.DATA.to_numpy(),
            "grupo": test.grupo.to_numpy(), "y_risco": truth, "K_fold": k,
            "pred_EWM3": ewm, "pred_media_historica_fixa": fixed,
            f"pred_{selected_model}": selected_pred,
        }))

        for scope, model, metadata in fitted_scopes:
            for item in model_importance(algorithm, model, features, metadata):
                final_importance_rows.append({
                    "fold": "treino_final", "target": target, "modelo": selected_model,
                    "tipo_alvo": "resíduo do EWM3" if residual_target else "contagem",
                    "escopo": scope, **item, "avaliacao": "treino_final",
                })

        # Train-residual checks for the selected Gaussian GAM residual model.
        if algorithm == "GAM" and residual_target and strategy == "global":
            train_resid = (train.y - train.ewm3).to_numpy() - np.asarray(metadata["train_prediction"])
            jb = jarque_bera(train_resid)
            fit_train = np.asarray(metadata["train_prediction"])
            try:
                bp_lm, bp_p, _, _ = het_breuschpagan(train_resid, sm.add_constant(fit_train, has_constant="add"))
            except Exception:
                bp_lm = bp_p = np.nan
            final_gam_diagnostics.append({
                "target": target, "fold": "treino_final", "modelo": selected_model,
                "escopo": "global", "escala_resposta": "correção do score de risco",
                "n_treino": len(train), "media_residuo_treino": float(np.mean(train_resid)),
                "desvio_residuo_treino": float(np.std(train_resid, ddof=1)),
                "assimetria_residuo_treino": float(skew(train_resid, bias=False)),
                "curtose_excesso_residuo_treino": float(kurtosis(train_resid, fisher=True, bias=False)),
                "jarque_bera_stat": float(jb.statistic), "jarque_bera_p": float(jb.pvalue),
                "breusch_pagan_lm": float(bp_lm), "breusch_pagan_p": float(bp_p),
                "corr_abs_residuo_ajustado_treino": float(np.corrcoef(np.abs(train_resid), fit_train)[0, 1]),
                "media_erro_validacao": float(np.mean(truth - selected_pred)),
                "sd_erro_validacao": float(np.std(truth - selected_pred, ddof=1)),
                "frac_previsao_no_limite_0_1": float(np.mean((selected_pred <= 0) | (selected_pred >= 1))),
            })

        holdout_error = pd.DataFrame({"H3": test.H3.to_numpy(), "DATA": test.DATA.to_numpy(),
                                      "erro": truth - selected_pred}).sort_values(["H3", "DATA"])
        holdout_error["lag1"] = holdout_error.groupby("H3").erro.shift(1)
        pairs = holdout_error.dropna(subset=["lag1"])
        test_autocorrelation_rows.append({
            "target": target, "fold": 4, "particao": "teste_reservado",
            "modelo": selected_model, "pares_H3_mes": len(pairs),
            "autocorrelacao_erro_lag1": pairs.erro.corr(pairs.lag1) if len(pairs) > 1 else np.nan,
        })
        selected_monthly = pd.DataFrame({"DATA": test.DATA.to_numpy(), "y": truth,
                                         "pred": selected_pred})
        for month, g in selected_monthly.groupby("DATA"):
            test_shape_rows.append({"target": target, "fold": 4, "particao": "teste_reservado",
                                    "modelo": selected_model, "escopo": "global", "segmento": "todos",
                                    "ajustado_medio": float(g.pred.mean()),
                                    "residuo_medio": float((g.y - g.pred).mean()),
                                    "sd_residuo": float((g.y - g.pred).std()), "n": len(g),
                                    "DATA": month})

    # Reuse comparison and diagnostics CSVs; flag records so the dashboard can
    # keep validation and untouched holdout results separate.
    cv["avaliacao"] = "validacao_temporal"
    test_summary = pd.DataFrame(selected_rows)
    summary_out = pd.concat([cv, test_summary], ignore_index=True, sort=False)
    summary_out.to_csv(summary_path, index=False)

    pred_path = OUT / "final_model_comparison_groups_h3_predictions.csv"
    old_predictions = pd.read_csv(pred_path, parse_dates=["DATA"]) if pred_path.exists() else pd.DataFrame()
    if not old_predictions.empty:
        if "particao" in old_predictions:
            old_predictions = old_predictions[old_predictions.particao.ne("teste_reservado")]
        old_predictions["particao"] = "validacao_temporal"
    pred_test = pd.concat(prediction_rows, ignore_index=True, sort=False)
    pd.concat([old_predictions, pred_test], ignore_index=True, sort=False).to_csv(pred_path, index=False)

    importance_path = OUT / "final_model_comparison_groups_h3_ebm_importance.csv"
    old_importance = pd.read_csv(importance_path) if importance_path.exists() else pd.DataFrame()
    if not old_importance.empty:
        if "avaliacao" in old_importance:
            old_importance = old_importance[old_importance.avaliacao.ne("treino_final")]
        old_importance["avaliacao"] = "validacao_temporal"
    final_importance = pd.DataFrame(final_importance_rows)
    pd.concat([old_importance, final_importance], ignore_index=True, sort=False).to_csv(importance_path, index=False)

    diagnostics_path = OUT / "diagnostics_ridge_h3_diagnostics.csv"
    old_diagnostics = pd.read_csv(diagnostics_path) if diagnostics_path.exists() else pd.DataFrame()
    if final_gam_diagnostics:
        if not old_diagnostics.empty:
            old_diagnostics = old_diagnostics[old_diagnostics.modelo.ne("GAM_resid_global")]
        pd.concat([old_diagnostics, pd.DataFrame(final_gam_diagnostics)], ignore_index=True, sort=False).to_csv(diagnostics_path, index=False)

    autocorr_path = OUT / "diagnostics_ridge_h3_temporal_error_autocorrelation.csv"
    old_autocorr = pd.read_csv(autocorr_path) if autocorr_path.exists() else pd.DataFrame()
    if not old_autocorr.empty:
        if "particao" in old_autocorr:
            old_autocorr = old_autocorr[old_autocorr.particao.ne("teste_reservado")]
        old_autocorr["particao"] = "validacao_temporal"
    pd.concat([old_autocorr, pd.DataFrame(test_autocorrelation_rows)], ignore_index=True, sort=False).to_csv(autocorr_path, index=False)

    shape_path = OUT / "diagnostics_ridge_h3_residual_shape_by_fitted_decile.csv"
    old_shape = pd.read_csv(shape_path) if shape_path.exists() else pd.DataFrame()
    if not old_shape.empty:
        if "particao" in old_shape:
            old_shape = old_shape[old_shape.particao.ne("teste_reservado")]
        old_shape["particao"] = "validacao_temporal"
    pd.concat([old_shape, pd.DataFrame(test_shape_rows)], ignore_index=True, sort=False).to_csv(shape_path, index=False)
    print("Teste reservado (2025-07 a 2026-06), modelos escolhidos na validação temporal:")
    print(test_summary[["target", "modelo", "RMSE_risco_medio", "MAE_risco_medio",
                        "ganho_medio_vs_EWM3_pct", "ganho_medio_vs_media_fixa_pct"]].to_string(index=False))
    print(f"\nResultados anexados aos CSVs existentes em {OUT}.")


def main():
    data = pd.read_csv(DATA_PATH, parse_dates=["DATA"], low_memory=False).sort_values(["H3", "DATA"]).reset_index(drop=True)
    data = data[data.DATA.between("2022-01-01", "2026-06-01")].copy()
    modeled = data[data.DATA.between("2023-01-01", "2025-06-01")].copy()
    metric_rows, pred_rows, group_rows, importance_rows = [], [], [], []
    ridge_diagnostic_rows, ridge_vif_rows, ridge_vif_cache, ridge_shape_rows = [], [], {}, []
    algorithms = ["RF", "Ridge", "Ridge_log1p", "GAM", "EBM"]

    for fold, (vstart, vend) in enumerate(FOLDS, 1):
        train0 = modeled[modeled.DATA < vstart].copy()
        valid0 = modeled[modeled.DATA.between(vstart, vend)].copy()
        for target, count_col in TARGETS.items():
            y_positive = train0.loc[train0[count_col] > 0, count_col]
            k = float(y_positive.quantile(.90)) if len(y_positive) else 1.
            history = history_table(data, count_col, k)
            train = train0.merge(history, on=["H3", "DATA"], how="left", validate="one_to_one")
            valid = valid0.merge(history, on=["H3", "DATA"], how="left", validate="one_to_one")
            features = FEATURES[target] + EXTRA
            totals = train.groupby("H3")[count_col].sum().sort_values(ascending=False, kind="stable")
            high_n = max(1, int(np.ceil(HIGH_SHARE * len(totals))))
            high_set = set(totals.head(high_n).index)
            train["grupo"] = np.where(train.H3.isin(high_set), "alto", "baixo")
            valid["grupo"] = np.where(valid.H3.isin(high_set), "alto", "baixo")
            high_train, low_train = train[train.grupo.eq("alto")].copy(), train[train.grupo.eq("baixo")].copy()
            high_valid, low_valid = valid[valid.grupo.eq("alto")].copy(), valid[valid.grupo.eq("baixo")].copy()
            high_mask, low_mask = valid.grupo.eq("alto").to_numpy(), valid.grupo.eq("baixo").to_numpy()
            low_hurdle_count = fit_low_hurdle(low_train, valid, count_col, FEATURES[target], k)
            truth = valid.y.to_numpy()
            cell_mean = train.groupby("H3").y.mean()
            preds = {
                "media_historica_fixa": valid.H3.map(cell_mean).fillna(float(train.y.mean())).to_numpy(),
                "EWM3": valid.ewm3.to_numpy(),
            }
            pred_counts = {}
            fold_importance_rows = []
            # Train each count algorithm on all H3s (ungrouped) and separately within each group.
            for algorithm in algorithms:
                all_count, all_model, all_extra = fit_count_model(algorithm, train, valid, count_col, features)
                preds[f"{algorithm}_global"] = score_count(all_count, k)
                pred_counts[f"{algorithm}_global"] = all_count
                high_count, high_model, high_extra = fit_count_model(algorithm, high_train, high_valid, count_col, features)
                low_count, low_model, low_extra = fit_count_model(algorithm, low_train, low_valid, count_col, features)
                for scope, fitted, metadata in [("global", all_model, all_extra),
                                                ("alto", high_model, high_extra),
                                                ("baixo", low_model, low_extra)]:
                    model_label = (f"{algorithm}_global" if scope == "global" else
                                   f"{algorithm}_grupos_mesmo_modelo")
                    for imp in model_importance(algorithm, fitted, features, metadata):
                        fold_importance_rows.append({"fold": fold, "target": target, "modelo": model_label,
                                                     "tipo_alvo": "contagem", "escopo": scope, **imp})
                    if scope == "alto":
                        for imp in model_importance(algorithm, fitted, features, metadata):
                            fold_importance_rows.append({"fold": fold, "target": target,
                                                         "modelo": f"{algorithm}_alto_HurdleNB_baixo",
                                                         "tipo_alvo": "contagem", "escopo": scope, **imp})
                if algorithm in {"Ridge", "Ridge_log1p"}:
                    response = np.log1p if algorithm == "Ridge_log1p" else np.asarray
                    ridge_diagnostics(target, fold, f"{algorithm}_global", "global", train, valid,
                                      features, all_model, response(train[count_col].to_numpy(dtype=float)),
                                      response(valid[count_col].to_numpy(dtype=float)), ridge_vif_cache,
                                      ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)
                    for scope, subset_train, subset_valid, fitted in [
                        ("alto", high_train, high_valid, high_model),
                        ("baixo", low_train, low_valid, low_model),
                    ]:
                        ridge_diagnostics(target, fold, f"{algorithm}_grupos_mesmo_modelo", scope,
                                          subset_train, subset_valid, features, fitted,
                                          response(subset_train[count_col].to_numpy(dtype=float)),
                                          response(subset_valid[count_col].to_numpy(dtype=float)),
                                          ridge_vif_cache, ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)
                    ridge_diagnostics(target, fold, f"{algorithm}_alto_HurdleNB_baixo", "alto",
                                      high_train, high_valid, features, high_model,
                                      response(high_train[count_col].to_numpy(dtype=float)),
                                      response(high_valid[count_col].to_numpy(dtype=float)),
                                      ridge_vif_cache, ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)
                grouped_count = np.empty(len(valid), dtype=float)
                grouped_count[high_mask] = high_count
                grouped_count[low_mask] = low_count
                preds[f"{algorithm}_grupos_mesmo_modelo"] = score_count(grouped_count, k)
                pred_counts[f"{algorithm}_grupos_mesmo_modelo"] = grouped_count

                # Alternative grouped strategy: specialized model on high group, fixed hurdle-NB on low.
                hybrid_count = low_hurdle_count.copy()
                hybrid_count[high_mask] = high_count
                preds[f"{algorithm}_alto_HurdleNB_baixo"] = score_count(hybrid_count, k)
                pred_counts[f"{algorithm}_alto_HurdleNB_baixo"] = hybrid_count


            # Corrections to the EWM3 forecast. Residuals can be negative, so
            # Ridge_log1p is not a mathematically valid transform for this target.
            for algorithm in ["RF", "Ridge", "GAM", "EBM"]:
                resid_global, model_global, meta_global = fit_residual_model(algorithm, train, valid, features)
                global_name = f"{algorithm}_resid_global"
                preds[global_name] = np.clip(valid.ewm3.to_numpy() + resid_global, 0, 1)
                for imp in model_importance(algorithm, model_global, features, meta_global):
                    fold_importance_rows.append({"fold": fold, "target": target, "modelo": global_name,
                                                 "tipo_alvo": "resíduo do EWM3", "escopo": "global", **imp})
                if algorithm == "Ridge":
                    ridge_diagnostics(target, fold, "Ridge_resid_global", "global", train, valid,
                                      features, model_global, (train.y - train.ewm3).to_numpy(),
                                      (valid.y - valid.ewm3).to_numpy(), ridge_vif_cache,
                                      ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)

                resid_high, model_high, meta_high = fit_residual_model(algorithm, high_train, high_valid, features)
                resid_low, model_low, meta_low = fit_residual_model(algorithm, low_train, low_valid, features)
                group_risk = np.empty(len(valid), dtype=float)
                group_risk[high_mask] = np.clip(valid.loc[high_mask, "ewm3"].to_numpy() + resid_high, 0, 1)
                group_risk[low_mask] = np.clip(valid.loc[low_mask, "ewm3"].to_numpy() + resid_low, 0, 1)
                group_name = f"{algorithm}_resid_grupos_mesmo_modelo"
                preds[group_name] = group_risk
                for scope, fitted, metadata in [("alto", model_high, meta_high), ("baixo", model_low, meta_low)]:
                    for imp in model_importance(algorithm, fitted, features, metadata):
                        fold_importance_rows.append({"fold": fold, "target": target, "modelo": group_name,
                                                     "tipo_alvo": "resíduo do EWM3", "escopo": scope, **imp})
                if algorithm == "Ridge":
                    for scope, subset_train, subset_valid, fitted in [
                        ("alto", high_train, high_valid, model_high),
                        ("baixo", low_train, low_valid, model_low),
                    ]:
                        ridge_diagnostics(target, fold, "Ridge_resid_grupos_mesmo_modelo", scope,
                                          subset_train, subset_valid, features, fitted,
                                          (subset_train.y - subset_train.ewm3).to_numpy(),
                                          (subset_valid.y - subset_valid.ewm3).to_numpy(),
                                          ridge_vif_cache, ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)

                hybrid = score_count(low_hurdle_count, k)
                hybrid[high_mask] = np.clip(valid.loc[high_mask, "ewm3"].to_numpy() + resid_high, 0, 1)
                hybrid_name = f"{algorithm}_resid_alto_HurdleNB_baixo"
                preds[hybrid_name] = hybrid
                for imp in model_importance(algorithm, model_high, features, meta_high):
                    fold_importance_rows.append({"fold": fold, "target": target, "modelo": hybrid_name,
                                                 "tipo_alvo": "resíduo do EWM3", "escopo": "alto", **imp})
                if algorithm == "Ridge":
                    ridge_diagnostics(target, fold, "Ridge_resid_alto_HurdleNB_baixo", "alto",
                                      high_train, high_valid, features, model_high,
                                      (high_train.y - high_train.ewm3).to_numpy(),
                                      (high_valid.y - high_valid.ewm3).to_numpy(),
                                      ridge_vif_cache, ridge_diagnostic_rows, ridge_vif_rows, ridge_shape_rows)
            importance_rows.extend(fold_importance_rows)

            grouped_hurdle_ewm = score_count(low_hurdle_count, k)
            grouped_hurdle_ewm[high_mask] = valid.loc[high_mask, "ewm3"].to_numpy()
            preds["EWM3_alto_HurdleNB_baixo"] = grouped_hurdle_ewm

            group_rows.append(pd.DataFrame({"fold": fold, "target": target, "H3": totals.index,
                                            "grupo": np.where(totals.index.isin(high_set), "alto", "baixo"),
                                            "share_alto": HIGH_SHARE, "contagem_treino": totals.values,
                                            "K_fold": k, "periodo_validacao_inicio": vstart,
                                            "periodo_validacao_fim": vend}))
            for name, prediction in preds.items():
                for segment, mask in [("todos", np.ones(len(valid), dtype=bool)), ("alto", high_mask), ("baixo", low_mask)]:
                    metric_rows.append({"fold": fold, "target": target, "modelo": name, "segmento": segment,
                                        "share_alto": HIGH_SHARE, "K_fold": k, "n": int(mask.sum()),
                                        "RMSE_risco": rmse(truth[mask], prediction[mask]),
                                        "MAE_risco": float(mean_absolute_error(truth[mask], prediction[mask])),
                                        "RMSE_contagem": rmse(valid.loc[mask, count_col].to_numpy(), pred_counts[name][mask]) if name in pred_counts else np.nan})
            pred_rows.append(pd.DataFrame({"fold": fold, "target": target, "H3": valid.H3.to_numpy(),
                                           "DATA": valid.DATA.to_numpy(), "grupo": valid.grupo.to_numpy(),
                                           "y_risco": truth, "K_fold": k,
                                           **{f"pred_{name}": p for name, p in preds.items()}}))

    metrics = pd.DataFrame(metric_rows)
    predictions = pd.concat(pred_rows, ignore_index=True)
    groups = pd.concat(group_rows, ignore_index=True)
    importances = pd.DataFrame(importance_rows)
    metrics.to_csv(OUT / "final_model_comparison_groups_h3_folds.csv", index=False)
    predictions.to_csv(OUT / "final_model_comparison_groups_h3_predictions.csv", index=False)
    groups.to_csv(OUT / "final_model_comparison_groups_h3_assignments.csv", index=False)
    importances.to_csv(OUT / "final_model_comparison_groups_h3_ebm_importance.csv", index=False)
    pd.DataFrame(ridge_diagnostic_rows).to_csv(OUT / "diagnostics_ridge_h3_diagnostics.csv", index=False)
    pd.DataFrame(ridge_vif_rows).to_csv(OUT / "diagnostics_ridge_h3_vif.csv", index=False)
    pd.DataFrame(ridge_shape_rows).to_csv(OUT / "diagnostics_ridge_h3_residual_shape_by_fitted_decile.csv", index=False)

    base = metrics[(metrics.modelo == "EWM3") & (metrics.segmento == "todos")][["fold", "target", "RMSE_risco"]].rename(columns={"RMSE_risco": "RMSE_EWM3"})
    fixed = metrics[(metrics.modelo == "media_historica_fixa") & (metrics.segmento == "todos")][["fold", "target", "RMSE_risco"]].rename(columns={"RMSE_risco": "RMSE_media_fixa"})
    all_metrics = metrics[metrics.segmento == "todos"].merge(base, on=["fold", "target"]).merge(fixed, on=["fold", "target"])
    all_metrics["ganho_vs_EWM3_pct"] = (all_metrics.RMSE_EWM3 - all_metrics.RMSE_risco) / all_metrics.RMSE_EWM3 * 100
    all_metrics["ganho_vs_media_fixa_pct"] = (all_metrics.RMSE_media_fixa - all_metrics.RMSE_risco) / all_metrics.RMSE_media_fixa * 100
    summary = all_metrics.groupby(["target", "modelo"], as_index=False).agg(
        folds=("fold", "nunique"), RMSE_risco_medio=("RMSE_risco", "mean"), MAE_risco_medio=("MAE_risco", "mean"),
        ganho_medio_vs_EWM3_pct=("ganho_vs_EWM3_pct", "mean"), ganho_medio_vs_media_fixa_pct=("ganho_vs_media_fixa_pct", "mean"),
        folds_melhor_EWM3=("ganho_vs_EWM3_pct", lambda s: int((s > 0).sum())),
        folds_melhor_media_fixa=("ganho_vs_media_fixa_pct", lambda s: int((s > 0).sum())))
    summary.to_csv(OUT / "final_model_comparison_groups_h3_summary.csv", index=False)
    group_effect_rows = []
    summary_lookup = summary.set_index(["target", "modelo"])
    for target in TARGETS:
        for algorithm in ["RF", "Ridge", "Ridge_log1p", "GAM", "EBM"]:
            configurations = [(algorithm, "")]
            if algorithm != "Ridge_log1p":
                configurations.append((f"{algorithm} (resíduo)", "_resid"))
            for label, suffix in configurations:
                global_rmse = float(summary_lookup.loc[(target, f"{algorithm}{suffix}_global"), "RMSE_risco_medio"])
                same_rmse = float(summary_lookup.loc[(target, f"{algorithm}{suffix}_grupos_mesmo_modelo"), "RMSE_risco_medio"])
                hybrid_rmse = float(summary_lookup.loc[(target, f"{algorithm}{suffix}_alto_HurdleNB_baixo"), "RMSE_risco_medio"])
                group_effect_rows.append({"target": target, "algoritmo": label,
                                          "RMSE_global": global_rmse, "RMSE_grupos_mesmo_modelo": same_rmse,
                                          "ganho_grupo_mesmo_modelo_pct": (global_rmse - same_rmse) / global_rmse * 100,
                                          "RMSE_grupo_alto_Hurdle_baixo": hybrid_rmse,
                                          "ganho_hibrido_vs_global_pct": (global_rmse - hybrid_rmse) / global_rmse * 100})
    pd.DataFrame(group_effect_rows).to_csv(OUT / "final_model_comparison_groups_h3_grouping_effect.csv", index=False)
    segment_summary = metrics.groupby(["target", "modelo", "segmento"], as_index=False).agg(
        RMSE_risco_medio=("RMSE_risco", "mean"), MAE_risco_medio=("MAE_risco", "mean"), RMSE_contagem_media=("RMSE_contagem", "mean"))
    segment_summary.to_csv(OUT / "final_model_comparison_groups_h3_segment_summary.csv", index=False)
    print("Comparação geral, média dos 3 folds:")
    print(summary.sort_values(["target", "RMSE_risco_medio"]).to_string(index=False))
    print("\nDesempenho por grupo:")
    print(segment_summary[segment_summary.modelo.isin(["EWM3", "RF_global", "Ridge_global", "Ridge_log1p_global", "GAM_global", "EBM_global",
          "RF_grupos_mesmo_modelo", "Ridge_grupos_mesmo_modelo", "Ridge_log1p_grupos_mesmo_modelo", "GAM_grupos_mesmo_modelo", "EBM_grupos_mesmo_modelo",
          "RF_alto_HurdleNB_baixo", "Ridge_alto_HurdleNB_baixo", "Ridge_log1p_alto_HurdleNB_baixo", "GAM_alto_HurdleNB_baixo", "EBM_alto_HurdleNB_baixo"])]
          .sort_values(["target", "segmento", "RMSE_risco_medio"]).to_string(index=False))
    print(f"\nArquivos gerados em {OUT}")
    evaluate_reserved_test()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reserved-test-only", action="store_true",
                        help="avalia os melhores modelos usando a comparação temporal já salva")
    args = parser.parse_args()
    if args.reserved_test_only:
        evaluate_reserved_test()
    else:
        main()
