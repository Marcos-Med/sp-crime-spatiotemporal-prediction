"""Final temporal comparison: RF, Ridge, NB-GAM and EBM, grouped vs ungrouped.

High/low groups are defined from training-only target counts (top 20%). Models
predict counts, then predictions are mapped to the existing bounded risk score.
The low-group hurdle hybrid is included as a separate, fixed low-activity setup.
"""
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.gam.api import BSplines, GLMGam
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from interpret.glassbox import ExplainableBoostingRegressor

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
        return np.maximum(pred, 0), fitted, (xtr, active)
    raise ValueError(name)


def main():
    data = pd.read_csv(DATA_PATH, parse_dates=["DATA"], low_memory=False).sort_values(["H3", "DATA"]).reset_index(drop=True)
    data = data[data.DATA.between("2022-01-01", "2026-06-01")].copy()
    modeled = data[data.DATA.between("2023-01-01", "2025-06-01")].copy()
    metric_rows, pred_rows, group_rows, ebm_rows = [], [], [], []
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
            # Train each count algorithm on all H3s (ungrouped) and separately within each group.
            for algorithm in algorithms:
                all_count, all_model, all_extra = fit_count_model(algorithm, train, valid, count_col, features)
                preds[f"{algorithm}_global"] = score_count(all_count, k)
                pred_counts[f"{algorithm}_global"] = all_count
                high_count, high_model, high_extra = fit_count_model(algorithm, high_train, high_valid, count_col, features)
                low_count, low_model, low_extra = fit_count_model(algorithm, low_train, low_valid, count_col, features)
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

                # Store interpretable EBM importances for all/global and grouped fits.
                if algorithm == "EBM":
                    for scope, model in [("global", all_model), ("alto", high_model), ("baixo", low_model)]:
                        for feat, importance in zip(model.term_names_, model.term_importances()):
                            ebm_rows.append({"fold": fold, "target": target, "escopo": scope,
                                             "feature": feat, "importancia_media_absoluta": float(importance)})

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
    importances = pd.DataFrame(ebm_rows)
    metrics.to_csv(OUT / "final_model_comparison_groups_h3_folds.csv", index=False)
    predictions.to_csv(OUT / "final_model_comparison_groups_h3_predictions.csv", index=False)
    groups.to_csv(OUT / "final_model_comparison_groups_h3_assignments.csv", index=False)
    importances.to_csv(OUT / "final_model_comparison_groups_h3_ebm_importance.csv", index=False)

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
            global_rmse = float(summary_lookup.loc[(target, f"{algorithm}_global"), "RMSE_risco_medio"])
            same_rmse = float(summary_lookup.loc[(target, f"{algorithm}_grupos_mesmo_modelo"), "RMSE_risco_medio"])
            hybrid_rmse = float(summary_lookup.loc[(target, f"{algorithm}_alto_HurdleNB_baixo"), "RMSE_risco_medio"])
            group_effect_rows.append({"target": target, "algoritmo": algorithm,
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


if __name__ == "__main__":
    main()
