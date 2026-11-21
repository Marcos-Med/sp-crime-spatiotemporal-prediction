"""Diagnostics and explanations for the high-activity Ridge residual model.

Run from the repository root or from processing_datasets. Outputs are written
to datasets/diagnostics_ridge_h3_*.csv.
"""
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import jarque_bera, skew, kurtosis
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor


ROOT = Path.cwd()
if ROOT.name == "processing_datasets":
    ROOT = ROOT.parent
SRC = ROOT / "datasets" / "database_processed_h3_risk.csv"
OUT = ROOT / "datasets"
TARGETS = {
    "RISCO_CRIME": "CNT_CRIME_COUNT",
    "RISCO_FURTO": "FURTO_COUNT",
    "RISCO_ROUBO": "ROUBO_COUNT",
}
FEATURES = {
    "RISCO_CRIME": ["crime_media_12m_log", "crime_razao_3_12", "crime_sazonal_12", "crime_pct_meses_12m", "crime_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_FURTO": ["furto_media_12m_log", "furto_razao_3_12", "furto_sazonal_12", "furto_pct_meses_12m", "furto_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
    "RISCO_ROUBO": ["roubo_media_12m_log", "roubo_razao_3_12", "roubo_sazonal_12", "roubo_viz_rel", "C_IPVS", "pop_total", "media_moradores", "pct_jovens_15_29", "taxa_alfabetizacao", "pct_negros", "pct_dom_casa", "pct_dom_apartamento", "pct_dom_cortico", "MES_SIN", "MES_COS", "SEM_DOMICILIOS"],
}
FOLDS = [("2024-01-01", "2024-06-01"), ("2024-07-01", "2024-12-01"), ("2025-01-01", "2025-06-01")]
ALPHA = 10.0
HIGH_SHARE = 0.20


def risk(count, k):
    return count.clip(lower=0) / (count.clip(lower=0) + k)


def metric_rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def make_history(frame, count_col, k):
    h = frame[["H3", "DATA", count_col]].copy()
    h["y"] = risk(h[count_col], k)
    h["ewm3"] = h.groupby("H3", sort=False)["y"].transform(
        lambda s: s.shift(1).ewm(halflife=3, adjust=False, min_periods=1).mean()
    )
    h["residual"] = h.y - h.ewm3
    h["resid_lag1"] = h.groupby("H3", sort=False).residual.shift(1)
    h["resid_mean3"] = h.groupby("H3", sort=False).residual.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    return h[["H3", "DATA", "y", "ewm3", "resid_lag1", "resid_mean3"]]


def main():
    if not SRC.exists():
        raise FileNotFoundError(f"Não encontrei a base: {SRC}")
    # The comparison notebook now writes Ridge diagnostics for direct and
    # EWM3-residual variants in global/grouped scopes. Preserve and display that
    # comprehensive result instead of overwriting it with the legacy high-only run.
    current_diagnostics = OUT / "diagnostics_ridge_h3_diagnostics.csv"
    if current_diagnostics.exists():
        current = pd.read_csv(current_diagnostics)
        if {"modelo", "escopo"}.issubset(current.columns):
            print("Diagnósticos multi-modelo atualizados pela comparação temporal:")
            print(current.groupby(["target", "modelo", "escopo"], as_index=False).agg(
                folds=("fold", "nunique"),
                jarque_bera_p_mediano=("jarque_bera_p", "median"),
                breusch_pagan_p_mediano=("breusch_pagan_p", "median"),
                erro_validacao_medio=("media_erro_validacao", "mean"),
            ).to_string(index=False))
            print(f"\nCSVs existentes preservados em: {OUT}")
            return
    data = pd.read_csv(SRC, parse_dates=["DATA"], low_memory=False)
    data = data.sort_values(["H3", "DATA"]).reset_index(drop=True)
    data = data[data.DATA.between("2022-01-01", "2026-06-01")].copy()
    train_period = data[data.DATA.between("2023-01-01", "2025-06-01")].copy()

    diagnostic_rows, importance_rows, coef_rows, local_rows, fold_rows, vif_rows, temporal_rows, linearity_rows = [], [], [], [], [], [], [], []
    for target, count_col in TARGETS.items():
        cols = FEATURES[target] + ["ewm3", "resid_lag1", "resid_mean3"]
        for fold, (vstart, vend) in enumerate(FOLDS, 1):
            train = train_period[train_period.DATA < vstart].copy()
            valid = train_period[train_period.DATA.between(vstart, vend)].copy()
            positives = train.loc[train[count_col] > 0, count_col]
            k = float(positives.quantile(.90)) if len(positives) else 1.0
            hist = make_history(data, count_col, k)
            tr = train.merge(hist, on=["H3", "DATA"], how="left", validate="one_to_one")
            va = valid.merge(hist, on=["H3", "DATA"], how="left", validate="one_to_one")
            totals = tr.groupby("H3")[count_col].sum().sort_values(ascending=False, kind="stable")
            high_n = max(1, int(np.ceil(HIGH_SHARE * len(totals))))
            high_cells = set(totals.head(high_n).index)
            tr = tr[tr.H3.isin(high_cells)].copy()
            va = va[va.H3.isin(high_cells)].copy()
            if tr.empty or va.empty:
                continue

            xtr = tr[cols].replace([np.inf, -np.inf], np.nan)
            xva = va[cols].replace([np.inf, -np.inf], np.nan)
            med = xtr.median().fillna(0)
            xtr, xva = xtr.fillna(med), xva.fillna(med)
            scaler = StandardScaler().fit(xtr)
            ztr = pd.DataFrame(scaler.transform(xtr), columns=cols, index=tr.index)
            zva = pd.DataFrame(scaler.transform(xva), columns=cols, index=va.index)
            ytr = (tr.y - tr.ewm3).to_numpy()
            yva = va.y.to_numpy()
            model = Ridge(alpha=ALPHA).fit(ztr, ytr)
            pred_resid = model.predict(zva)
            pred = np.clip(va.ewm3.to_numpy() + pred_resid, 0, 1)
            errors = yva - pred
            temporal_rows.extend({"target": target, "fold": fold, "H3": h3, "DATA": date, "erro_validacao": float(err)}
                                 for h3, date, err in zip(va.H3, va.DATA, errors))
            fold_rows.append({"target": target, "fold": fold, "validacao_inicio": vstart, "validacao_fim": vend,
                              "n_treino_alto": len(tr), "n_validacao_alto": len(va), "rmse_ridge_residual": metric_rmse(yva, pred),
                              "rmse_ewm3": metric_rmse(yva, va.ewm3.to_numpy()), "alpha": ALPHA})

            # Classical regression checks on training residuals are descriptive
            # only: Ridge is being used for prediction, not coefficient inference.
            train_fit_resid = ytr - model.predict(ztr)
            jb = jarque_bera(train_fit_resid)
            try:
                bp_lm, bp_p, bp_f, bp_fp = het_breuschpagan(train_fit_resid, sm.add_constant(ztr, has_constant="add"))
            except Exception:
                bp_lm = bp_p = bp_f = bp_fp = np.nan
            fitted = model.predict(ztr)
            fitted_bins = pd.qcut(pd.Series(fitted), q=10, duplicates="drop")
            shape = pd.DataFrame({"faixa": fitted_bins, "ajustado": fitted, "residuo": train_fit_resid}).groupby("faixa", observed=True).agg(
                ajustado_medio=("ajustado", "mean"), residuo_medio=("residuo", "mean"),
                sd_residuo=("residuo", "std"), n=("residuo", "size")).reset_index(drop=True)
            for _, binrow in shape.iterrows():
                linearity_rows.append({"target": target, "fold": fold, **binrow.to_dict()})
            diagnostic_rows.append({
                "target": target, "fold": fold, "n_treino_alto": len(tr),
                "media_residuo_treino": float(np.mean(train_fit_resid)),
                "desvio_residuo_treino": float(np.std(train_fit_resid, ddof=1)),
                "assimetria_residuo_treino": float(skew(train_fit_resid, bias=False)),
                "curtose_excesso_residuo_treino": float(kurtosis(train_fit_resid, fisher=True, bias=False)),
                "jarque_bera_stat": float(jb.statistic), "jarque_bera_p": float(jb.pvalue),
                "breusch_pagan_lm": float(bp_lm), "breusch_pagan_p": float(bp_p),
                "corr_abs_residuo_ajustado_treino": float(np.corrcoef(np.abs(train_fit_resid), fitted)[0, 1]),
                "media_erro_validacao": float(np.mean(errors)), "sd_erro_validacao": float(np.std(errors, ddof=1)),
                "frac_previsao_no_limite_0_1": float(np.mean((va.ewm3.to_numpy() + pred_resid <= 0) | (va.ewm3.to_numpy() + pred_resid >= 1))),
            })

            # VIF is a diagnostic for redundant inputs; high values do not
            # invalidate predictive use, but make individual coefficients less stable.
            for j, col in enumerate(cols):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    vif = variance_inflation_factor(ztr.to_numpy(), j)
                vif_rows.append({"target": target, "fold": fold, "feature": col, "VIF": float(vif)})

            # Standardized Ridge contributions explain the residual correction.
            coef = pd.Series(model.coef_, index=cols)
            for col in cols:
                coef_rows.append({"target": target, "fold": fold, "feature": col,
                                  "coef_padronizado": float(coef[col]),
                                  "coef_original_unidade": float(coef[col] / scaler.scale_[cols.index(col)])})
            contrib = zva.mul(coef, axis=1)
            for row_pos, (_, row) in enumerate(va.iterrows()):
                values = contrib.iloc[row_pos]
                top = values.abs().nlargest(5).index
                for rank, col in enumerate(top, 1):
                    local_rows.append({"target": target, "fold": fold, "H3": row.H3, "DATA": row.DATA,
                                       "y_observado": float(row.y), "ewm3_base": float(row.ewm3),
                                       "residuo_ridge_previsto": float(pred_resid[row_pos]),
                                       "intercepto_ridge_residuo": float(model.intercept_),
                                       "risco_previsto_final": float(pred[row_pos]), "feature": col,
                                       "contribuicao_ao_residuo": float(values[col]), "rank_abs_contribuicao": rank})

            # Holdout permutation importance: increase in residual-prediction RMSE.
            base_rmse = metric_rmse(yva - va.ewm3.to_numpy(), pred_resid)
            rng = np.random.default_rng(1100 + fold)
            for col in cols:
                increases = []
                for _ in range(5):
                    perm = zva.copy()
                    perm[col] = rng.permutation(perm[col].to_numpy())
                    increases.append(metric_rmse(yva - va.ewm3.to_numpy(), model.predict(perm)) - base_rmse)
                importance_rows.append({"target": target, "fold": fold, "feature": col,
                                        "delta_RMSE_permutacao": float(np.mean(increases)),
                                        "sd_delta_RMSE": float(np.std(increases, ddof=1))})

    temporal = pd.DataFrame(temporal_rows)
    lag_pairs = []
    if not temporal.empty:
        temporal = temporal.sort_values(["target", "fold", "H3", "DATA"])
        temporal["erro_lag1"] = temporal.groupby(["target", "fold", "H3"]).erro_validacao.shift(1)
        for target, g in temporal.dropna(subset=["erro_lag1"]).groupby("target"):
            lag_pairs.append({"target": target, "pares_H3_mes": len(g),
                              "autocorrelacao_erro_lag1": float(g.erro_validacao.corr(g.erro_lag1))})
    outputs = {
        "diagnostics": pd.DataFrame(diagnostic_rows),
        "importance": pd.DataFrame(importance_rows),
        "coefficients": pd.DataFrame(coef_rows),
        "local_contributions": pd.DataFrame(local_rows),
        "fold_metrics": pd.DataFrame(fold_rows),
        "vif": pd.DataFrame(vif_rows),
        "temporal_error_autocorrelation": pd.DataFrame(lag_pairs),
        "residual_shape_by_fitted_decile": pd.DataFrame(linearity_rows),
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / f"diagnostics_ridge_h3_{name}.csv", index=False)

    print("Diagnósticos por alvo/fold (testes clássicos são descritivos para Ridge):")
    print(outputs["diagnostics"].to_string(index=False))
    print("\nImportância por permutação, média entre folds (delta RMSE > 0 indica utilidade):")
    imp = outputs["importance"].groupby(["target", "feature"], as_index=False).agg(
        delta_RMSE_permutacao=("delta_RMSE_permutacao", "mean"), folds_positivos=("delta_RMSE_permutacao", lambda s: int((s > 0).sum())))
    print(imp.sort_values(["target", "delta_RMSE_permutacao"], ascending=[True, False]).groupby("target").head(8).to_string(index=False))
    print("\nMétricas Ridge vs EWMA3 no grupo alto:")
    print(outputs["fold_metrics"].to_string(index=False))
    print(f"\nCSVs salvos em: {OUT}")


if __name__ == "__main__":
    main()
