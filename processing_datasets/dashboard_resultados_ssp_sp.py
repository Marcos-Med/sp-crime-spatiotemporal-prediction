from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "datasets"

FILES = {
    "comparacao": "final_model_comparison_groups_h3_summary.csv",
    "segmentos": "final_model_comparison_groups_h3_segment_summary.csv",
    "efeito_grupos": "final_model_comparison_groups_h3_grouping_effect.csv",
    "folds": "final_model_comparison_groups_h3_folds.csv",
    "ewm_comparacao": "evidence_why_ewm3_h3_model_comparison.csv",
    "persistencia": "evidence_why_ewm3_h3_temporal_persistence.csv",
    "residuo": "evidence_why_ewm3_h3_residual_learnability.csv",
    "validacao_residuos": "validation_target_specific_residual_h3_summary.csv",
    "diagnosticos": "diagnostics_ridge_h3_diagnostics.csv",
    "vif": "diagnostics_ridge_h3_vif.csv",
    "importancia": "diagnostics_ridge_h3_importance.csv",
    "contagem": "validation_explainable_count_models_h3_comparison.csv",
}


st.set_page_config(
    page_title="Resultados | Previsão de crimes em H3",
    page_icon="📍",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_csv(filename: str) -> pd.DataFrame | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, low_memory=False)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.warning(f"Não consegui ler `{filename}`: {exc}")
        return None


data = {key: load_csv(filename) for key, filename in FILES.items()}


def get_data(key: str) -> pd.DataFrame:
    frame = data.get(key)
    return frame.copy() if frame is not None else pd.DataFrame()


def fmt(value, digits=4, suffix="") -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}{suffix}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value, digits=1) -> str:
    return fmt(value, digits, "%")


st.title("Painel dos resultados")
st.caption(
    "Previsão de risco criminal por célula H3 · validação temporal · "
    "período de treino de 2023 a junho de 2025; 2022 não entra no treino."
)

comparison = get_data("comparacao")
if comparison.empty:
    st.error(
        "Ainda não encontrei os resultados da comparação principal. Execute "
        "`final_model_comparison_groups_h3.ipynb` e confira se os CSVs estão em `datasets/`."
    )
    st.stop()

targets = [t for t in ["RISCO_CRIME", "RISCO_ROUBO", "RISCO_FURTO"] if t in comparison["target"].unique()]
target_labels = {
    "RISCO_CRIME": "Crime (furto + roubo)",
    "RISCO_ROUBO": "Roubo",
    "RISCO_FURTO": "Furto",
}

with st.sidebar:
    st.header("Filtros")
    target = st.selectbox(
        "Alvo",
        targets,
        format_func=lambda x: target_labels.get(x, x),
    )
    st.divider()
    st.caption("Os gráficos usam os CSVs gerados pelos notebooks. Reexecute o app depois de atualizar esses arquivos.")

overview, groups_tab, ewm_tab, explain_tab, validation_tab, files_tab = st.tabs(
    ["Visão geral", "Grupos", "EWM3", "Explicabilidade", "Validações", "Arquivos"]
)


with overview:
    target_results = comparison[comparison["target"] == target].copy()
    target_results = target_results.sort_values("RMSE_risco_medio")
    baselines = target_results[target_results["modelo"].str.lower() == "ewm3"]
    candidates = target_results[target_results["modelo"].str.lower() != "ewm3"]
    best = candidates.iloc[0] if not candidates.empty else None
    ewm = baselines.iloc[0] if not baselines.empty else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Melhor modelo testado", best["modelo"] if best is not None else "—")
    c2.metric("RMSE do melhor modelo", fmt(best["RMSE_risco_medio"]) if best is not None else "—")
    c3.metric("RMSE do EWM3", fmt(ewm["RMSE_risco_medio"]) if ewm is not None else "—")
    c4.metric(
        "Ganho sobre EWM3",
        pct(best["ganho_medio_vs_EWM3_pct"]) if best is not None else "—",
        help="Valor positivo significa RMSE menor que o EWM3; negativo significa que o modelo perdeu para o EWM3.",
    )

    if best is not None:
        if best["ganho_medio_vs_EWM3_pct"] > 0:
            st.success(f"Para {target_labels.get(target, target)}, o melhor modelo desta comparação superou o EWM3 na média dos folds.")
        else:
            st.info(f"Para {target_labels.get(target, target)}, nenhum modelo testado superou o EWM3 na média dos folds.")

    st.subheader("Comparação dos modelos")
    chart = target_results.sort_values("RMSE_risco_medio", ascending=True)
    chart["tipo"] = chart["modelo"].apply(lambda x: "Baseline EWM3" if x.lower() == "ewm3" else "Modelo")
    fig = px.bar(
        chart,
        x="RMSE_risco_medio",
        y="modelo",
        color="tipo",
        orientation="h",
        color_discrete_map={"Baseline EWM3": "#d97706", "Modelo": "#2563eb"},
        labels={"RMSE_risco_medio": "RMSE médio (menor é melhor)", "modelo": "Modelo", "tipo": ""},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        target_results[
            [
                "modelo",
                "folds",
                "RMSE_risco_medio",
                "MAE_risco_medio",
                "ganho_medio_vs_EWM3_pct",
                "ganho_medio_vs_media_fixa_pct",
                "folds_melhor_EWM3",
            ]
        ].rename(
            columns={
                "modelo": "Modelo",
                "folds": "Folds",
                "RMSE_risco_medio": "RMSE médio",
                "MAE_risco_medio": "MAE médio",
                "ganho_medio_vs_EWM3_pct": "Ganho vs EWM3 (%)",
                "ganho_medio_vs_media_fixa_pct": "Ganho vs média fixa (%)",
                "folds_melhor_EWM3": "Folds em que venceu EWM3",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption("RMSE e MAE são calculados no score de risco. Ganho positivo indica erro menor que a referência.")


with groups_tab:
    st.subheader("O que a divisão entre células de alta e baixa atividade mudou?")
    grouping = get_data("efeito_grupos")
    grouping = grouping[grouping.get("target", pd.Series(dtype=str)) == target] if not grouping.empty else grouping
    if grouping.empty:
        st.info("Ainda não há CSV de efeito dos grupos.")
    else:
        grouping_long = grouping.melt(
            id_vars="algoritmo",
            value_vars=["RMSE_global", "RMSE_grupos_mesmo_modelo", "RMSE_grupo_alto_Hurdle_baixo"],
            var_name="estrategia",
            value_name="RMSE",
        )
        grouping_long["estrategia"] = grouping_long["estrategia"].map(
            {
                "RMSE_global": "Um modelo global",
                "RMSE_grupos_mesmo_modelo": "Mesmo algoritmo por grupo",
                "RMSE_grupo_alto_Hurdle_baixo": "Modelo alto + Hurdle baixo",
            }
        )
        fig = px.bar(
            grouping_long,
            x="algoritmo",
            y="RMSE",
            color="estrategia",
            barmode="group",
            labels={"algoritmo": "Algoritmo", "RMSE": "RMSE (menor é melhor)", "estrategia": "Estratégia"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(grouping.drop(columns="target").rename(columns={
            "algoritmo": "Algoritmo",
            "RMSE_global": "RMSE global",
            "RMSE_grupos_mesmo_modelo": "RMSE, mesmo modelo por grupo",
            "ganho_grupo_mesmo_modelo_pct": "Ganho desta divisão (%)",
            "RMSE_grupo_alto_Hurdle_baixo": "RMSE, alto + Hurdle baixo",
            "ganho_hibrido_vs_global_pct": "Ganho híbrido vs global (%)",
        }), hide_index=True, use_container_width=True)

    segment = get_data("segmentos")
    segment = segment[segment["target"] == target] if not segment.empty else segment
    if not segment.empty:
        models = sorted(segment["modelo"].dropna().unique())
        selected_model = st.selectbox("Ver erro por grupo para", models, key="segment_model")
        rows = segment[segment["modelo"] == selected_model]
        fig = px.bar(
            rows,
            x="segmento",
            y="RMSE_risco_medio",
            color="segmento",
            labels={"segmento": "Grupo", "RMSE_risco_medio": "RMSE médio do risco"},
        )
        st.plotly_chart(fig, use_container_width=True)


with ewm_tab:
    st.subheader("Por que o EWM3 é uma referência forte?")
    st.write("O EWM3 usa ocorrências passadas da própria célula, dando mais peso aos meses recentes. A comparação abaixo resume o quanto os outros modelos reduziram o RMSE em relação a ele.")
    evidence = get_data("ewm_comparacao")
    evidence = evidence[evidence["target"] == target] if not evidence.empty else evidence
    if evidence.empty:
        st.info("Execute `evidence_why_ewm3_strong_h3.ipynb` para gerar estas evidências.")
    else:
        fig = px.bar(
            evidence.sort_values("ganho_medio_vs_EWM3_pct"),
            x="ganho_medio_vs_EWM3_pct",
            y="modelo",
            color="escopo",
            orientation="h",
            labels={"ganho_medio_vs_EWM3_pct": "Ganho de RMSE vs EWM3 (%)", "modelo": "Modelo", "escopo": "Escopo"},
        )
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("À direita de zero: superou EWM3. À esquerda: ficou atrás.")

    persistence = get_data("persistencia")
    persistence = persistence[persistence["target"] == target] if not persistence.empty else persistence
    if not persistence.empty:
        st.markdown("**Persistência temporal nas células**")
        st.dataframe(persistence[[c for c in ["fold", "corr_intra_H3_atual_lag1", "corr_intra_H3_atual_EWM3", "RMSE_lag1", "RMSE_EWM3_recalculada", "RMSE_media_fixa", "ganho_EWM3_vs_media_pct"] if c in persistence]].rename(columns={
            "fold": "Fold",
            "corr_intra_H3_atual_lag1": "Correlação com mês anterior",
            "corr_intra_H3_atual_EWM3": "Correlação com EWM3",
            "RMSE_lag1": "RMSE, mês anterior",
            "RMSE_EWM3_recalculada": "RMSE, EWM3",
            "RMSE_media_fixa": "RMSE, média fixa",
            "ganho_EWM3_vs_media_pct": "Ganho EWM3 vs média fixa (%)",
        }), hide_index=True, use_container_width=True)

    learnability = get_data("residuo")
    learnability = learnability[learnability["target"] == target] if not learnability.empty else learnability
    if not learnability.empty:
        st.markdown("**O erro do EWM3 é previsível pelos modelos?**")
        fig = px.bar(
            learnability,
            x="fold",
            y=["RMSE_EWM3", "RMSE_Ridge_residual"],
            barmode="group",
            labels={"fold": "Fold", "value": "RMSE", "variable": "Previsão"},
            color_discrete_sequence=["#d97706", "#2563eb"],
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Ajustar o resíduo só ajuda se a correção reduzir o erro fora da amostra; compare os dois RMSEs em cada fold.")


with explain_tab:
    st.subheader("Explicabilidade e diagnósticos do Ridge")
    diagnostics = get_data("diagnosticos")
    diagnostics = diagnostics[diagnostics["target"] == target] if not diagnostics.empty else diagnostics
    if diagnostics.empty:
        st.info("Ainda não há diagnósticos do Ridge. Execute `diagnostics_explainability_ridge_h3.ipynb`.")
    else:
        dcols = st.columns(4)
        dcols[0].metric("Folds analisados", str(diagnostics["fold"].nunique()))
        dcols[1].metric("p-valor mediano (Jarque–Bera)", fmt(diagnostics["jarque_bera_p"].median(), 4))
        dcols[2].metric("p-valor mediano (Breusch–Pagan)", fmt(diagnostics["breusch_pagan_p"].median(), 4))
        dcols[3].metric("Erro médio de validação", fmt(diagnostics["media_erro_validacao"].mean()))
        st.caption("p-valores pequenos sinalizam evidência contra normalidade dos resíduos ou variância constante. Isso orienta a interpretação; não invalida automaticamente a previsão.")
        st.dataframe(diagnostics, hide_index=True, use_container_width=True)

    vif = get_data("vif")
    vif = vif[vif["target"] == target] if not vif.empty else vif
    if not vif.empty:
        st.markdown("**Multicolinearidade (VIF)**")
        vif_mean = vif.groupby("feature", as_index=False)["VIF"].median().sort_values("VIF", ascending=False).head(20)
        fig = px.bar(vif_mean.sort_values("VIF"), x="VIF", y="feature", orientation="h", labels={"VIF": "VIF mediano entre folds", "feature": "Feature"})
        fig.add_vline(x=5, line_dash="dash", annotation_text="5")
        fig.add_vline(x=10, line_dash="dot", annotation_text="10")
        st.plotly_chart(fig, use_container_width=True)

    importance = get_data("importancia")
    importance = importance[importance["target"] == target] if not importance.empty else importance
    if not importance.empty:
        st.markdown("**Features associadas à redução do erro (permutação)**")
        imp = importance.groupby("feature", as_index=False)["delta_RMSE_permutacao"].mean().sort_values("delta_RMSE_permutacao").tail(20)
        fig = px.bar(imp, x="delta_RMSE_permutacao", y="feature", orientation="h", labels={"delta_RMSE_permutacao": "Aumento médio do RMSE ao embaralhar", "feature": "Feature"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Valores maiores indicam que embaralhar a feature piorou mais a previsão. Isso mede contribuição preditiva, não causalidade.")


with validation_tab:
    st.subheader("Outras validações")
    residual_validation = get_data("validacao_residuos")
    if not residual_validation.empty:
        residual_validation = residual_validation[residual_validation["target"] == target]
        shares = sorted(residual_validation["share_high"].dropna().unique())
        if shares:
            share = st.selectbox("Proporção classificada como alta atividade", shares, format_func=lambda x: pct(x * 100, 0), key="share_high")
            sub = residual_validation[residual_validation["share_high"] == share].copy()
            segment = st.selectbox("Segmento", sorted(sub["segmento"].dropna().unique()), key="resid_segment")
            sub = sub[sub["segmento"] == segment].sort_values("RMSE_mean")
            st.dataframe(sub.rename(columns={
                "modelo": "Modelo", "folds": "Folds", "RMSE_mean": "RMSE médio", "MAE_mean": "MAE médio", "R2_mean": "R² médio", "gain_vs_ewm3_pct": "Ganho vs EWM3 (%)", "gain_vs_mean_pct": "Ganho vs média fixa (%)", "folds_better_than_ewm3": "Folds em que venceu EWM3",
            }), hide_index=True, use_container_width=True)
    else:
        st.info("CSV da validação de resíduos ainda não encontrado.")

    counts = get_data("contagem")
    counts = counts[counts["target"] == target] if not counts.empty else counts
    if not counts.empty:
        st.markdown("**Modelos explicáveis para contagem**")
        st.dataframe(counts.sort_values("RMSE_risco_medio").rename(columns={
            "modelo": "Modelo", "RMSE_risco_medio": "RMSE médio", "ganho_vs_ewm3_pct": "Ganho vs EWM3 (%)", "folds_melhor_ewm3": "Folds em que venceu EWM3", "ganho_vs_media_fixa_pct": "Ganho vs média fixa (%)", "n_folds": "Folds",
        }), hide_index=True, use_container_width=True)


with files_tab:
    st.subheader("Estado dos resultados")
    status = pd.DataFrame(
        [
            {
                "Notebook / análise": key.replace("_", " ").title(),
                "Arquivo esperado": filename,
                "Status": "Disponível" if (DATA_DIR / filename).exists() else "Ainda não gerado",
            }
            for key, filename in FILES.items()
        ]
    )
    st.dataframe(status, hide_index=True, use_container_width=True)
    st.caption(f"Pasta de leitura: `{DATA_DIR}`. O dashboard lê apenas os resultados já salvos; não executa notebooks nem modelos.")

