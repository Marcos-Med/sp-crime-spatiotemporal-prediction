"""Temporal comparison of high-group Negative Binomial GAM and EBM.

Targets are modeled as counts and mapped back to the existing bounded risk
score with the fold-specific K. The low group uses the established hurdle-NB.
Run from repository root or processing_datasets.
"""
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.gam.api import BSplines, GLMGam
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from interpret.glassbox import ExplainableBoostingRegressor
except ImportError:
    ExplainableBoostingRegressor = None

ROOT = Path.cwd()
if ROOT.name == "processing_datasets":
    ROOT = ROOT.parent
SRC = ROOT / "datasets" / "database_processed_h3_risk.csv"
OUT = ROOT / "datasets"
TARGETS = {"RISCO_CRIME": "CNT_CRIME_COUNT", "RISCO_FURTO": "FURTO_COUNT", "RISCO_ROUBO": "ROUBO_COUNT"}
FEATURES = {
    "RISCO_CRIME": ["crime_media_12m_log", "crime_razao_3_12", "crime_sazonal_12", "crime_pct_meses_12m", "crime_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_FURTO": ["furto_media_12m_log", "furto_razao_3_12", "furto_sazonal_12", "furto_pct_meses_12m", "furto_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_ROUBO": ["roubo_media_12m_log", "roubo_razao_3_12", "roubo_sazonal_12", "roubo_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
}
PERIODS = [("2024-01-01", "2024-06-01"), ("2024-07-01", "2024-12-01"), ("2025-01-01", "2025-06-01")]
HIGH_SHARE = 0.20
RIDGE_FEATURES_EXTRA = ["ewm3", "resid_lag1", "resid_mean3"]


def risk(count, k):
    count = np.maximum(np.asarray(count, dtype=float), 0)
    return count / (count + k)


def rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def mae(y, p):
    return float(mean_absolute_error(y, p))


def finite_design(train, other, cols):
    a = train[cols].replace([np.inf, -np.inf], np.nan)
    b = other[cols].replace([np.inf, -np.inf], np.nan)
    med = a.median().fillna(0)
    return a.fillna(med), b.fillna(med)


def make_history(data, count_col, k):
    h = data[["H3", "DATA", count_col]].copy()
    h["y"] = risk(h[count_col], k)
    h["ewm3"] = h.groupby("H3", sort=False).y.transform(lambda s: s.shift(1).ewm(halflife=3, adjust=False, min_periods=1).mean())
    h["residual"] = h.y - h.ewm3
    h["resid_lag1"] = h.groupby("H3", sort=False).residual.shift(1)
    h["resid_mean3"] = h.groupby("H3", sort=False).residual.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    return h[["H3", "DATA", "y", "ewm3", "resid_lag1", "resid_mean3"]]


def fit_low_hurdle(lo, va, count_col, features, k):
    xlo, xva = finite_design(lo, va, features)
    event = (lo[count_col] > 0).astype(int)
    classifier = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=2000, random_state=42))
    classifier.fit(xlo, event)
    p_event = classifier.predict_proba(xva)[:, 1]
    positive = event.eq(1)
    pos_counts = lo.loc[positive, count_col].astype(float)
    mu, var = float(pos_counts.mean()), float(pos_counts.var())
    alpha = max((var - mu) / (mu * mu), .01) if mu > 0 else .01
    scaler = StandardScaler().fit(xlo)
    x_pos = sm.add_constant(scaler.transform(xlo.loc[positive]), has_constant="add")
    x_test = sm.add_constant(scaler.transform(xva), has_constant="add")
    nb = sm.GLM(pos_counts.to_numpy(), x_pos, family=sm.families.NegativeBinomial(alpha=alpha)).fit(maxiter=100, disp=0)
    return p_event * np.maximum(nb.predict(x_test), 0)


def fit_nb_gam(train, valid, count_col, features):
    # Smooth all non-seasonal/non-binary features; retain sine/cosine seasonality
    # and the binary SEM_DOMICILIOS indicator as linear terms.
    linear = [c for c in features if c in {"MES_SIN", "MES_COS", "SEM_DOMICILIOS"}]
    smooth = [c for c in features if c not in linear]
    xtr, xva = finite_design(train, valid, features)
    med = xtr.median().fillna(0)
    # Reuse the fold-trained medians and standardization for stable spline bases.
    scaler = StandardScaler().fit(xtr)
    ztr = pd.DataFrame(scaler.transform(xtr), columns=features, index=train.index)
    zva = pd.DataFrame(scaler.transform(xva), columns=features, index=valid.index)
    smooth_train = ztr[smooth].copy()
    smooth_valid = zva[smooth].copy()
    # Remove any constant inputs before spline construction.
    active = [c for c in smooth if smooth_train[c].nunique(dropna=True) > 1]
    smooth_train = smooth_train[active]
    smooth_valid = smooth_valid[active]
    for col in active:
        lo, hi = float(smooth_train[col].min()), float(smooth_train[col].max())
        eps = max((hi - lo) * 1e-6, 1e-8)
        smooth_train[col] = smooth_train[col].clip(lo + eps, hi - eps)
        smooth_valid[col] = smooth_valid[col].clip(lo + eps, hi - eps)
    linear_train = sm.add_constant(ztr[linear], has_constant="add")
    linear_valid = sm.add_constant(zva[linear], has_constant="add")
    y = train[count_col].astype(float).to_numpy()
    avg, var = float(y.mean()), float(y.var())
    alpha = max((var - avg) / (avg * avg), .01) if avg > 0 else .01
    smoother = BSplines(smooth_train, df=[4] * len(active), degree=[3] * len(active))
    model = GLMGam(y, exog=linear_train, smoother=smoother,
                   family=sm.families.NegativeBinomial(alpha=alpha), alpha=0.1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.fit(maxiter=150, method="pirls")
    pred = np.asarray(result.predict(exog=linear_valid, exog_smooth=smooth_valid), dtype=float)
    return np.maximum(pred, 0), float(alpha), result, scaler, active, linear, xtr


def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    data = pd.read_csv(SRC, parse_dates=["DATA"], low_memory=False).sort_values(["H3", "DATA"]).reset_index(drop=True)
    data = data[data.DATA.between("2022-01-01", "2026-06-01")].copy()
    period_data = data[data.DATA.between("2023-01-01", "2025-06-01")].copy()
    rows, high_rows, explain_rows, shape_rows, local_rows, gam_effect_rows = [], [], [], [], [], []
    for fold, (vstart, vend) in enumerate(PERIODS, 1):
        tr0 = period_data[period_data.DATA < vstart].copy()
        va0 = period_data[period_data.DATA.between(vstart, vend)].copy()
        for target, count_col in TARGETS.items():
            features = FEATURES[target] + RIDGE_FEATURES_EXTRA
            pos = tr0.loc[tr0[count_col] > 0, count_col]
            k = float(pos.quantile(.90)) if len(pos) else 1.
            hist = make_history(data, count_col, k)
            tr = tr0.merge(hist, on=["H3", "DATA"], how="left", validate="one_to_one")
            va = va0.merge(hist, on=["H3", "DATA"], how="left", validate="one_to_one")
            totals = tr.groupby("H3")[count_col].sum().sort_values(ascending=False, kind="stable")
            n_high = max(1, int(np.ceil(HIGH_SHARE * len(totals))))
            high_cells = set(totals.head(n_high).index)
            tr["grupo"] = np.where(tr.H3.isin(high_cells), "alta", "baixa")
            va["grupo"] = np.where(va.H3.isin(high_cells), "alta", "baixa")
            hi, lo = tr[tr.grupo.eq("alta")].copy(), tr[tr.grupo.eq("baixa")].copy()
            vhi = va[va.grupo.eq("alta")].copy()
            if hi.empty or vhi.empty:
                continue
            low_count_all = fit_low_hurdle(lo, va, count_col, FEATURES[target], k)
            is_high = va.grupo.eq("alta").to_numpy()
            low_risk_all = risk(low_count_all, k)
            truth_risk = va.y.to_numpy()
            ewm_global = va.ewm3.to_numpy()
            mean_cell = tr.groupby("H3").y.mean()
            mean_hist = va.H3.map(mean_cell).fillna(float(tr.y.mean())).to_numpy()

            # High-group Negative Binomial GAM predicts counts, then maps them to risk.
            gam_count, gam_alpha, gam_fit, gam_scaler, smooth_features, linear_features, gam_x = fit_nb_gam(hi, vhi, count_col, features)
            gam_risk_hi = risk(gam_count, k)
            gam_combined = low_risk_all.copy(); gam_combined[is_high] = gam_risk_hi
            for smooth_idx, feature in enumerate(smooth_features):
                partial, _ = gam_fit.partial_values(smooth_idx, include_constant=False)
                xb = gam_x[feature].to_numpy(dtype=float)
                bins = pd.qcut(pd.Series(xb), q=10, duplicates="drop")
                curve = pd.DataFrame({"x": xb, "effect": np.asarray(partial), "bin": bins})
                curve = curve.groupby("bin", observed=True).agg(valor_feature_medio=("x", "mean"),
                                                               contribuicao_media_escala_link=("effect", "mean"), n=("effect", "size"))
                for _, point in curve.iterrows():
                    gam_effect_rows.append({"target": target, "fold": fold, "feature": feature,
                                            "tipo_efeito": "suavizado", **point.to_dict()})
            exog_names = list(gam_fit.model.exog_names[:gam_fit.model.k_exog_linear])
            for i, name in enumerate(exog_names):
                if name == "const":
                    continue
                gam_effect_rows.append({"target": target, "fold": fold, "feature": name,
                                        "tipo_efeito": "linear_padronizado",
                                        "valor_feature_medio": np.nan,
                                        "contribuicao_media_escala_link": float(gam_fit.params.iloc[i]), "n": len(hi)})
            predictions = {"ewm3_global": ewm_global, "media_historica_fixa": mean_hist,
                           "hurdle_baixa_ewm3_alta": np.where(is_high, ewm_global, low_risk_all),
                           "hurdle_baixa_nb_gam_alta": gam_combined}
            counts_predictions = {"nb_gam_alta": gam_count}

            # EBM with Poisson deviance: a nonnegative count prediction and native additive explanations.
            ebm = None
            if ExplainableBoostingRegressor is not None:
                xhi, xvhi = finite_design(hi, vhi, features)
                ebm = ExplainableBoostingRegressor(
                    feature_names=features, interactions=0, objective="poisson_deviance",
                    max_rounds=900, early_stopping_rounds=0, outer_bags=1,
                    validation_size=0, learning_rate=0.03, max_leaves=2,
                    min_samples_leaf=20, n_jobs=-1, random_state=42)
                ebm.fit(xhi, hi[count_col].astype(float))
                ebm_count = np.maximum(ebm.predict(xvhi), 0)
                ebm_risk_hi = risk(ebm_count, k)
                ebm_combined = low_risk_all.copy(); ebm_combined[is_high] = ebm_risk_hi
                predictions["hurdle_baixa_ebm_poisson_alta"] = ebm_combined
                counts_predictions["ebm_poisson_alta"] = ebm_count
                # Save global term importance and effect curves for explainability.
                for j, (feat, imp) in enumerate(zip(ebm.term_names_, ebm.term_importances())):
                    explain_rows.append({"target": target, "fold": fold, "feature": feat, "importance": float(imp)})
                for j, feat in enumerate(ebm.term_names_):
                    if j >= len(ebm.term_scores_):
                        continue
                    scores = np.asarray(ebm.term_scores_[j]).reshape(-1)
                    bins = ebm.bins_[j][0] if j < len(ebm.bins_) and len(ebm.bins_[j]) else np.arange(len(scores))
                    if len(bins) != len(scores):
                        bins = np.arange(len(scores))
                    for bin_id, (bin_x, score_value) in enumerate(zip(bins, scores)):
                        shape_rows.append({"target": target, "fold": fold, "feature": feat,
                                           "bin": bin_id, "valor_feature_bin": str(bin_x),
                                           "contribuicao_escala_link": float(score_value)})
                local_terms = np.asarray(ebm.eval_terms(xvhi))
                if local_terms.ndim == 3 and local_terms.shape[-1] == 1:
                    local_terms = local_terms[:, :, 0]
                for i in range(len(vhi)):
                    order = np.argsort(np.abs(local_terms[i]))[::-1][:5]
                    for rank, term_idx in enumerate(order, 1):
                        local_rows.append({"target": target, "fold": fold, "H3": vhi.iloc[i].H3,
                                           "DATA": vhi.iloc[i].DATA, "K_fold": k,
                                           "contagem_observada": float(vhi.iloc[i][count_col]),
                                           "risco_observado": float(vhi.iloc[i].y),
                                           "contagem_prevista_ebm": float(ebm_count[i]),
                                           "risco_previsto_ebm": float(ebm_risk_hi[i]),
                                           "intercepto_link_ebm": float(np.asarray(ebm.intercept_).reshape(-1)[0]),
                                           "feature": ebm.term_names_[term_idx],
                                           "contribuicao_link": float(local_terms[i, term_idx]),
                                           "rank_abs_contribuicao": rank})

            y_count = va[count_col].to_numpy(dtype=float)
            for model_name, p in predictions.items():
                hi_mask = is_high
                if model_name == "hurdle_baixa_nb_gam_alta":
                    high_count_pred = gam_count
                elif model_name == "hurdle_baixa_ebm_poisson_alta" and ebm is not None:
                    high_count_pred = counts_predictions["ebm_poisson_alta"]
                else:
                    high_count_pred = None
                rows.append({"fold": fold, "target": target, "modelo": model_name,
                             "periodo_inicio": vstart, "periodo_fim": vend, "share_alto": HIGH_SHARE,
                             "K_fold": k, "n_total": len(va), "RMSE_risco": rmse(truth_risk, p),
                             "MAE_risco": mae(truth_risk, p),
                             "RMSE_contagem_alta": rmse(vhi[count_col].to_numpy(), high_count_pred) if high_count_pred is not None else np.nan})
                high_rows.append({"fold": fold, "target": target, "modelo": model_name,
                                  "RMSE_risco_alto": rmse(vhi.y.to_numpy(), p[hi_mask]),
                                  "MAE_risco_alto": mae(vhi.y.to_numpy(), p[hi_mask]),
                                  "RMSE_contagem_alta": rmse(vhi[count_col].to_numpy(), high_count_pred) if high_count_pred is not None else np.nan,
                                  "MAE_contagem_alta": mae(vhi[count_col].to_numpy(), high_count_pred) if high_count_pred is not None else np.nan,
                                  "alpha_nb_gam": gam_alpha if model_name == "hurdle_baixa_nb_gam_alta" else np.nan})

    df = pd.DataFrame(rows)
    high = pd.DataFrame(high_rows)
    explain = pd.DataFrame(explain_rows)
    shape = pd.DataFrame(shape_rows)
    local = pd.DataFrame(local_rows)
    df.to_csv(OUT / "validation_explainable_count_models_h3_folds.csv", index=False)
    high.to_csv(OUT / "validation_explainable_count_models_h3_high_metrics.csv", index=False)
    explain.to_csv(OUT / "validation_explainable_count_models_h3_ebm_importance.csv", index=False)
    shape.to_csv(OUT / "validation_explainable_count_models_h3_ebm_shapes.csv", index=False)
    local.to_csv(OUT / "validation_explainable_count_models_h3_ebm_local.csv", index=False)
    pd.DataFrame(gam_effect_rows).to_csv(OUT / "validation_explainable_count_models_h3_gam_effects.csv", index=False)
    summary = df.groupby(["target", "modelo"], as_index=False).agg(folds=("fold", "nunique"), RMSE_risco_medio=("RMSE_risco", "mean"), MAE_risco_medio=("MAE_risco", "mean"))
    summary.to_csv(OUT / "validation_explainable_count_models_h3_summary.csv", index=False)
    compare_rows = []
    for target, group in df.groupby("target"):
        for model_name, candidate in group.groupby("modelo"):
            ewm = group[group.modelo.eq("ewm3_global")].set_index("fold").RMSE_risco
            hist = group[group.modelo.eq("media_historica_fixa")].set_index("fold").RMSE_risco
            cand = candidate.set_index("fold").RMSE_risco
            common = cand.index.intersection(ewm.index).intersection(hist.index)
            compare_rows.append({"target": target, "modelo": model_name,
                                 "RMSE_risco_medio": float(cand.loc[common].mean()),
                                 "ganho_vs_ewm3_pct": float(((ewm.loc[common] - cand.loc[common]) / ewm.loc[common] * 100).mean()),
                                 "folds_melhor_ewm3": int((cand.loc[common] < ewm.loc[common]).sum()),
                                 "ganho_vs_media_fixa_pct": float(((hist.loc[common] - cand.loc[common]) / hist.loc[common] * 100).mean()),
                                 "folds_melhor_media_fixa": int((cand.loc[common] < hist.loc[common]).sum()),
                                 "n_folds": len(common)})
    comparison = pd.DataFrame(compare_rows)
    comparison.to_csv(OUT / "validation_explainable_count_models_h3_comparison.csv", index=False)
    high_summary = high.groupby(["target", "modelo"], as_index=False).agg(folds=("fold", "nunique"), RMSE_risco_alto=("RMSE_risco_alto", "mean"), MAE_risco_alto=("MAE_risco_alto", "mean"), RMSE_contagem_alta=("RMSE_contagem_alta", "mean"), alpha_nb_gam=("alpha_nb_gam", "mean"))
    high_summary.to_csv(OUT / "validation_explainable_count_models_h3_high_summary.csv", index=False)
    print("Resumo no conjunto todo:")
    print(summary.to_string(index=False))
    print("\nResumo do grupo alto:")
    print(high_summary.to_string(index=False))
    if ExplainableBoostingRegressor is None:
        print("\nEBM não executado: pacote InterpretML ausente. A comparação GAM foi executada.")
    else:
        print("\nPrincipais importâncias EBM por alvo:")
        print(explain.groupby(["target", "feature"], as_index=False).importance.mean().sort_values(["target", "importance"], ascending=[True, False]).groupby("target").head(8).to_string(index=False))
    print(f"\nSaídas em {OUT}")


if __name__ == "__main__":
    main()
