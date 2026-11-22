"""Create empirical evidence tables for why EWMA3 is a strong benchmark."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error

ROOT = Path.cwd()
if ROOT.name == "processing_datasets":
    ROOT = ROOT.parent
D = ROOT / "datasets"


def rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def main():
    # Results from the final count-model comparison, already evaluated OOF.
    summary = pd.read_csv(D / "final_model_comparison_groups_h3_summary.csv")
    if "avaliacao" in summary:
        summary = summary[summary.avaliacao.eq("validacao_temporal")].copy()
    folds = pd.read_csv(D / "final_model_comparison_groups_h3_folds.csv")
    grouping = pd.read_csv(D / "final_model_comparison_groups_h3_grouping_effect.csv")
    pred = pd.read_csv(D / "final_model_comparison_groups_h3_predictions.csv", parse_dates=["DATA"])
    if "particao" in pred:
        pred = pred[pred.particao.eq("validacao_temporal")].copy()
    assignments = pd.read_csv(D / "final_model_comparison_groups_h3_assignments.csv")

    # Keep every tested direct and residual configuration visible against EWM3.
    best_rows = []
    for target in summary.target.unique():
        g = summary[summary.target.eq(target)].set_index("modelo")
        for name, row in g.iterrows():
            if name in {"EWM3", "media_historica_fixa"}:
                scope = "baseline"
            elif "_resid_" in name:
                scope = "residuo_" + name.split("_resid_", 1)[1]
            elif name.endswith("_global"):
                scope = "global"
            elif name.endswith("_grupos_mesmo_modelo"):
                scope = "grupos_mesmo_modelo"
            elif name.endswith("_alto_HurdleNB_baixo"):
                scope = "alto_modelo_baixo_hurdle"
            else:
                scope = "outro"
            best_rows.append({"target": target, "escopo": scope, "modelo": name,
                              "RMSE_medio": row.RMSE_risco_medio,
                              "ganho_medio_vs_EWM3_pct": row.ganho_medio_vs_EWM3_pct,
                              "folds_melhor_EWM3": int(row.folds_melhor_EWM3),
                              "ganho_medio_vs_media_fixa_pct": row.ganho_medio_vs_media_fixa_pct})
    best_df = pd.DataFrame(best_rows)
    best_df.to_csv(D / "evidence_why_ewm3_h3_model_comparison.csv", index=False)

    # Per-fold comparison of EWMA3, fixed per-cell historical mean, and leading candidates.
    chosen = {}
    best_by_target = {}
    for target in summary.target.unique():
        target_summary = summary[summary.target.eq(target)]
        best_by_target[target] = str(target_summary.sort_values("RMSE_risco_medio").iloc[0].modelo)
        residuals = target_summary[target_summary.modelo.str.contains("_resid_", regex=False)]
        if not residuals.empty:
            best_by_target[f"{target}_resid"] = str(residuals.sort_values("RMSE_risco_medio").iloc[0].modelo)
        chosen[target] = list(dict.fromkeys([
            "EWM3", "media_historica_fixa", best_by_target[target],
            *([best_by_target[f"{target}_resid"]] if f"{target}_resid" in best_by_target else []),
        ]))
    fold_rows = []
    for target, names in chosen.items():
        for name in names:
            sub = folds[(folds.target == target) & (folds.segmento == "todos") & (folds.modelo == name)]
            for _, r in sub.iterrows():
                fold_rows.append({"fold": r.fold, "target": target, "modelo": name,
                                  "RMSE_risco": r.RMSE_risco, "MAE_risco": r.MAE_risco,
                                  "fonte": "comparacao_final"})
    fold_df = pd.DataFrame(fold_rows)
    fold_df.to_csv(D / "evidence_why_ewm3_h3_fold_metrics.csv", index=False)

    # Temporal persistence evidence: observed risk vs last-month risk / EWM3.
    raw = pd.read_csv(D / "database_processed_h3_risk.csv", parse_dates=["DATA"], low_memory=False)
    raw = raw.sort_values(["H3", "DATA"])
    count_cols = {"RISCO_CRIME": "CNT_CRIME_COUNT", "RISCO_FURTO": "FURTO_COUNT", "RISCO_ROUBO": "ROUBO_COUNT"}
    persistence_rows = []
    for (fold, target), g in pred.groupby(["fold", "target"]):
        k = float(g.K_fold.iloc[0])
        valid_start = g.DATA.min()
        count_col = count_cols[target]
        h = raw[["H3", "DATA", count_col]].copy()
        h["y"] = h[count_col].clip(lower=0) / (h[count_col].clip(lower=0) + k)
        by_cell = h.groupby("H3", sort=False).y
        h["risco_lag1"] = by_cell.shift(1)
        h["risco_lag3"] = by_cell.shift(3)
        h["ewm3_calculada"] = h.groupby("H3", sort=False).y.transform(
            lambda s: s.shift(1).ewm(halflife=3, adjust=False, min_periods=1).mean())
        v = g.merge(h[["H3", "DATA", "y", "risco_lag1", "risco_lag3", "ewm3_calculada"]],
                    on=["H3", "DATA"], how="left", validate="one_to_one")
        # Remove stable between-cell level differences; this correlation is
        # the relevant diagnostic for month-to-month persistence within H3.
        train_hist = h[h.DATA.between("2023-01-01", valid_start - pd.offsets.MonthBegin(1))]
        cell_level = train_hist.groupby("H3").y.mean()
        v["nivel_H3_treino"] = v.H3.map(cell_level).fillna(float(train_hist.y.mean()))
        v["desvio_atual_H3"] = v.y - v.nivel_H3_treino
        v["desvio_lag1_H3"] = v.risco_lag1 - v.nivel_H3_treino
        v["desvio_EWM3_H3"] = v.ewm3_calculada - v.nivel_H3_treino
        persistence_rows.append({"fold": fold, "target": target, "n": len(v),
                                 "corr_bruta_atual_lag1_entre_H3": v.y.corr(v.risco_lag1),
                                 "corr_bruta_atual_EWM3_entre_H3": v.y.corr(v.ewm3_calculada),
                                 "corr_intra_H3_atual_lag1": v.desvio_atual_H3.corr(v.desvio_lag1_H3),
                                 "corr_intra_H3_atual_EWM3": v.desvio_atual_H3.corr(v.desvio_EWM3_H3),
                                 "RMSE_lag1": rmse(v.y, v.risco_lag1),
                                 "RMSE_EWM3_recalculada": rmse(v.y, v.ewm3_calculada),
                                 "RMSE_media_fixa": rmse(v.y, v.pred_media_historica_fixa),
                                 "ganho_EWM3_vs_media_pct": (rmse(v.y, v.pred_media_historica_fixa) - rmse(v.y, v.ewm3_calculada)) / rmse(v.y, v.pred_media_historica_fixa) * 100})
    persistence = pd.DataFrame(persistence_rows)
    persistence.to_csv(D / "evidence_why_ewm3_h3_temporal_persistence.csv", index=False)

    # Does the best residual model from the main comparison learn the EWM3 error?
    residual_rows = []
    for target in summary.target.unique():
        model_name = best_by_target.get(f"{target}_resid")
        if model_name is None:
            continue
        resid_pred = pred[pred.target.eq(target)].copy()
        pred_col = f"pred_{model_name}"
        if pred_col not in resid_pred:
            continue
        for fold, g in resid_pred.groupby("fold"):
            real_error = g.y_risco - g.pred_EWM3
            correction = g[pred_col] - g.pred_EWM3
            corrected_prediction = g.pred_EWM3 + correction
            rmse_ewm = rmse(g.y_risco, g.pred_EWM3)
            rmse_corrected = rmse(g.y_risco, corrected_prediction)
            residual_rows.append({"fold": fold, "target": target, "modelo": model_name, "n": len(g),
                              "RMSE_EWM3": rmse_ewm, "RMSE_modelo_residual": rmse_corrected,
                              "corr_erro_real_correcao": real_error.corr(correction),
                              "MAE_erro_EWM3": float(np.mean(np.abs(real_error))),
                              "MAE_correcao": float(np.mean(np.abs(correction))),
                              "frac_previsoes_corrigidas": float(np.mean(np.abs(correction) > 1e-12))})
    residual = pd.DataFrame(residual_rows)
    residual.to_csv(D / "evidence_why_ewm3_h3_residual_learnability.csv", index=False)

    # How much crime burden the top 20% group captures in the training folds.
    concentration_rows = []
    for (fold, target), g in assignments.groupby(["fold", "target"]):
        total = g.contagem_treino.sum()
        high = g.loc[g.grupo.eq("alto"), "contagem_treino"].sum()
        concentration_rows.append({"fold": fold, "target": target, "share_H3_alto": .20,
                                   "frac_contagens_no_grupo_alto": high / total if total else np.nan,
                                   "n_H3_total": len(g), "n_H3_alto": int(g.grupo.eq("alto").sum())})
    concentration = pd.DataFrame(concentration_rows)
    concentration.to_csv(D / "evidence_why_ewm3_h3_group_concentration.csv", index=False)

    print("1) Baselines e melhores algoritmos por escopo:")
    print(best_df.sort_values(["target", "escopo", "RMSE_medio"]).to_string(index=False))
    print("\n2) Persistência temporal na validação (média dos folds):")
    print(persistence.groupby("target").agg(corr_intra_H3_lag1=("corr_intra_H3_atual_lag1", "mean"),
          corr_intra_H3_EWM3=("corr_intra_H3_atual_EWM3", "mean"), RMSE_lag1=("RMSE_lag1", "mean"),
          RMSE_EWM3=("RMSE_EWM3_recalculada", "mean"), RMSE_media=("RMSE_media_fixa", "mean"),
          ganho_EWM3_vs_media_pct=("ganho_EWM3_vs_media_pct", "mean")).to_string())
    print("\n3) Correções Ridge residuais fora da amostra:")
    print(residual.to_string(index=False))
    print("\n4) Concentração no top 20% de H3:")
    print(concentration.groupby("target").frac_contagens_no_grupo_alto.agg(["mean", "min", "max"]).to_string())
    print("\n5) Features que mais explicam o erro residual da EWMA3:")
    print(importance_summary.sort_values(["target", "delta_RMSE_permutacao"], ascending=[True, False]).groupby("target").head(6).to_string(index=False))
    print(f"\nTabelas salvas em {D} com prefixo evidence_why_ewm3_h3_.")


if __name__ == "__main__":
    main()
