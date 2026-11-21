from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "datasets"

FILES = {
    "comparacao": "final_model_comparison_groups_h3_summary.csv",
    "predicoes": "final_model_comparison_groups_h3_predictions.csv",
    "segmentos": "final_model_comparison_groups_h3_segment_summary.csv",
    "efeito_grupos": "final_model_comparison_groups_h3_grouping_effect.csv",
    "folds": "final_model_comparison_groups_h3_folds.csv",
    "ewm_comparacao": "evidence_why_ewm3_h3_model_comparison.csv",
    "persistencia": "evidence_why_ewm3_h3_temporal_persistence.csv",
    "residuo": "evidence_why_ewm3_h3_residual_learnability.csv",
    "validacao_residuos": "validation_target_specific_residual_h3_summary.csv",
    "diagnosticos": "diagnostics_ridge_h3_diagnostics.csv",
    "vif": "diagnostics_ridge_h3_vif.csv",
    "importancia": "final_model_comparison_groups_h3_ebm_importance.csv",
    "autocorrelacao": "diagnostics_ridge_h3_temporal_error_autocorrelation.csv",
    "forma_residuo": "diagnostics_ridge_h3_residual_shape_by_fitted_decile.csv",
    "contagem": "validation_explainable_count_models_h3_comparison.csv",
}


st.set_page_config(
    page_title="Resultados | Previsão de crimes em H3",
    page_icon="📍",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_csv(filename: str, modified_ns: int | None) -> pd.DataFrame | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, low_memory=False)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.warning(f"Não consegui ler `{filename}`: {exc}")
        return None


data = {
    key: load_csv(
        filename,
        (DATA_DIR / filename).stat().st_mtime_ns if (DATA_DIR / filename).exists() else None,
    )
    for key, filename in FILES.items()
}


def get_data(key: str) -> pd.DataFrame:
    frame = data.get(key)
    return frame.copy() if frame is not None else pd.DataFrame()


def fmt(value, digits=4, suffix="") -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}{suffix}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value, digits=1) -> str:
    return fmt(value, digits, "%")


def model_label(name: str) -> str:
    if name == "EWM3":
        return "Baseline EWM3"
    if name == "media_historica_fixa":
        return "Baseline média histórica fixa"
    residual = "_resid_" in name
    if residual:
        algorithm, strategy = name.split("_resid_", 1)
        prefix = f"{algorithm} · correção do resíduo EWM3 · "
    else:
        suffixes = ["_grupos_mesmo_modelo", "_alto_HurdleNB_baixo", "_global"]
        suffix = next((value for value in suffixes if name.endswith(value)), None)
        algorithm = name[:-len(suffix)] if suffix else name
        strategy = suffix[1:] if suffix else name
        prefix = f"{algorithm} · previsão direta · "
    strategies = {
        "global": "global",
        "grupos_mesmo_modelo": "um modelo por grupo",
        "alto_HurdleNB_baixo": "grupo alto + Hurdle no baixo",
    }
    if strategy == "alto_HurdleNB_baixo":
        return prefix + strategies[strategy]
    if strategy.endswith("_alto_HurdleNB_baixo"):
        return prefix + strategies["alto_HurdleNB_baixo"]
    return prefix + strategies.get(strategy, strategy)


st.title("Painel dos resultados")
st.caption(
    "Previsão de risco criminal por célula H3 · validação temporal e teste reservado · "
    "treino de jan/2023 a jun/2025; teste reservado de jul/2025 a jun/2026. 2022 não entra no treino."
)

comparison_all = get_data("comparacao")
if comparison_all.empty:
    st.error(
        "Ainda não encontrei os resultados da comparação principal. Execute "
        "`final_model_comparison_groups_h3.ipynb` e confira se os CSVs estão em `datasets/`."
    )
    st.stop()
comparison = comparison_all
if "avaliacao" in comparison:
    comparison = comparison[comparison.avaliacao.eq("validacao_temporal")].copy()

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

overview, test_tab, groups_tab, ewm_tab, explain_tab, validation_tab, files_tab = st.tabs(
    ["Visão geral", "Teste reservado", "Grupos", "EWM3", "Explicabilidade", "Validações", "Arquivos"]
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
    st.caption("As variantes de resíduos aprendem o erro restante depois do EWM3 e somam a correção à previsão. Ridge_log1p não tem variante residual: o resíduo pode ser negativo, então log1p não se aplica a ele.")

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


with test_tab:
    st.subheader("Resultado no conjunto reservado")
    reserved_results = comparison_all
    if "avaliacao" in reserved_results:
        reserved_results = reserved_results[reserved_results.avaliacao.eq("teste_reservado")]
    reserved_results = reserved_results[reserved_results.target == target] if not reserved_results.empty else reserved_results
    if reserved_results.empty:
        st.warning("O teste reservado ainda não foi calculado. Execute `python processing_datasets/final_model_comparison_groups_h3.py --reserved-test-only` na raiz do projeto.")
    else:
        final_rows = reserved_results[~reserved_results.modelo.isin(["EWM3", "media_historica_fixa", "EWM3_alto_HurdleNB_baixo"])]
        if final_rows.empty:
            st.warning("Não encontrei o modelo final selecionado para este alvo.")
        else:
            final_row = final_rows.iloc[0]
            selected_final_model = final_row.modelo
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Modelo escolhido na validação", model_label(selected_final_model))
            c2.metric("RMSE no teste", fmt(final_row.RMSE_risco_medio))
            c3.metric("Ganho vs EWM3", pct(final_row.ganho_medio_vs_EWM3_pct))
            c4.metric("Meses reservados", str(final_row.meses_teste))

            st.dataframe(reserved_results[[
                "modelo", "RMSE_risco_medio", "MAE_risco_medio",
                "ganho_medio_vs_EWM3_pct", "ganho_medio_vs_media_fixa_pct",
                "n_teste", "H3_teste", "meses_teste",
            ]].rename(columns={
                "modelo": "Modelo", "RMSE_risco_medio": "RMSE no teste",
                "MAE_risco_medio": "MAE no teste", "ganho_medio_vs_EWM3_pct": "Ganho vs EWM3 (%)",
                "ganho_medio_vs_media_fixa_pct": "Ganho vs média fixa (%)",
                "n_teste": "Registros", "H3_teste": "Células H3", "meses_teste": "Meses",
            }), hide_index=True, use_container_width=True)

            pred = get_data("predicoes")
            if not pred.empty and "particao" in pred:
                pred = pred[(pred.particao == "teste_reservado") & (pred.target == target)].copy()
            if not pred.empty:
                pred["DATA"] = pd.to_datetime(pred["DATA"])
                model_col = f"pred_{selected_final_model}"
                if model_col in pred:
                    series = {
                        "EWM3": "pred_EWM3",
                        "Média histórica fixa": "pred_media_historica_fixa",
                        model_label(selected_final_model): model_col,
                    }
                    monthly = []
                    for month, month_data in pred.groupby("DATA"):
                        for label, col in series.items():
                            if col in month_data and month_data[col].notna().any():
                                monthly.append({"mês": pd.to_datetime(month), "modelo": label,
                                                "RMSE": ((month_data.y_risco - month_data[col]) ** 2).mean() ** .5})
                    monthly = pd.DataFrame(monthly)
                    if not monthly.empty:
                        st.markdown("**RMSE por mês do teste reservado**")
                        fig = px.line(monthly, x="mês", y="RMSE", color="modelo", markers=True,
                                      labels={"mês": "Mês", "RMSE": "RMSE do risco", "modelo": "Previsão"})
                        st.plotly_chart(fig, use_container_width=True)
                        st.dataframe(monthly.pivot(index="mês", columns="modelo", values="RMSE").reset_index(),
                                     hide_index=True, use_container_width=True)
            st.info("O modelo foi ajustado uma vez com jan/2023–jun/2025. O teste cobre jul/2025–jun/2026. A avaliação é rolling de um mês à frente: observações anteriores dentro do período reservado atualizam as features históricas, mas não há novo ajuste do modelo.")


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
        st.info(
            "Este gráfico separa a **avaliação** por faixa de atividade. "
            "Escolher `EBM_global` significa que um único EBM foi treinado com todas as células; "
            "as barras `alto` e `baixo` apenas medem como esse mesmo modelo foi em cada recorte. "
            "A barra `todos` mede o erro no conjunto completo. Modelos com nomes como "
            "`EBM_grupos_mesmo_modelo` ou `EBM_alto_HurdleNB_baixo` usam estratégias separadas por grupo."
        )
        models = sorted(segment["modelo"].dropna().unique())
        selected_model = st.selectbox("Modelo a avaliar", models, key="segment_model")
        rows = segment[segment["modelo"] == selected_model]
        fig = px.bar(
            rows,
            x="segmento",
            y="RMSE_risco_medio",
            color="segmento",
            labels={"segmento": "Recorte avaliado", "RMSE_risco_medio": "RMSE médio do risco"},
        )
        fig.update_layout(legend_title_text="Recorte avaliado")
        st.plotly_chart(fig, use_container_width=True)


with ewm_tab:
    st.subheader("Por que o EWM3 é uma referência forte?")
    st.write("O EWM3 usa ocorrências passadas da própria célula, dando mais peso aos meses recentes. A comparação abaixo resume o quanto os outros modelos reduziram o RMSE em relação a ele.")
    evidence = get_data("ewm_comparacao")
    evidence = evidence[evidence["target"] == target] if not evidence.empty else evidence
    if evidence.empty:
        st.info("Execute `evidence_why_ewm3_strong_h3.ipynb` para gerar estas evidências.")
    else:
        scope_options = ["Todos"] + sorted(evidence["escopo"].dropna().unique())
        selected_evidence_scope = st.selectbox("Estratégia comparada", scope_options, key="ewm_scope")
        if selected_evidence_scope != "Todos":
            evidence = evidence[evidence["escopo"] == selected_evidence_scope]
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
    st.subheader("Explicabilidade do modelo final")
    reserved_rows = comparison_all
    if "avaliacao" in reserved_rows:
        reserved_rows = reserved_rows[reserved_rows.avaliacao.eq("teste_reservado")]
    reserved_rows = reserved_rows[reserved_rows.target == target] if not reserved_rows.empty else reserved_rows
    baselines_for_explain = {"EWM3", "media_historica_fixa", "EWM3_alto_HurdleNB_baixo"}
    final_models = reserved_rows[~reserved_rows.modelo.isin(baselines_for_explain)] if not reserved_rows.empty else reserved_rows
    if final_models.empty:
        st.warning("O teste reservado ainda não escolheu o modelo final. Execute o teste reservado primeiro.")
    else:
        selected_model = str(final_models.iloc[0].modelo)
        st.markdown(f"**Alvo:** {target_labels.get(target, target)}  \n**Modelo treinado:** {model_label(selected_model)}")
        importance_all = get_data("importancia")
        if not importance_all.empty:
            importance = importance_all[
                importance_all.target.eq(target)
                & importance_all.modelo.eq(selected_model)
                & importance_all.get("avaliacao", pd.Series(index=importance_all.index, dtype=str)).eq("treino_final")
            ].copy()
        else:
            importance = pd.DataFrame()
        if importance.empty:
            st.info("As importâncias do ajuste final ainda não estão salvas. Execute `python processing_datasets/final_model_comparison_groups_h3.py --reserved-test-only`.")
        else:
            importance = importance.groupby(["feature", "metodo_importancia"], as_index=False).agg(
                importancia=("importancia", "mean"), coeficiente_padronizado=("coeficiente_padronizado", "mean")
            ).sort_values("importancia", ascending=False)
            fig = px.bar(
                importance.head(20).sort_values("importancia"), x="importancia", y="feature",
                color="metodo_importancia", orientation="h",
                labels={"importancia": "Importância no modelo ajustado", "feature": "Feature", "metodo_importancia": "Método"},
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Importância calculada no modelo ajustado somente com o treino. Ela descreve contribuição preditiva, não causalidade.")

        if selected_model.startswith("RF"):
            st.info("Random Forest não tem coeficientes lineares nem pressupostos clássicos de OLS. A importância por redução de impureza ajuda a priorizar variáveis preditivas, mas não mede efeito causal.")
        elif selected_model.startswith("GAM"):
            st.info("GAM é uma regressão aditiva com efeitos suaves. As features importantes incluem magnitudes das bases spline; elas não são coeficientes lineares únicos por feature.")
            diagnostics = get_data("diagnosticos")
            if not diagnostics.empty:
                diagnostics = diagnostics[(diagnostics.target == target) & (diagnostics.modelo == selected_model)]
            if not diagnostics.empty:
                row = diagnostics.iloc[-1]
                c1, c2, c3 = st.columns(3)
                c1.metric("p-valor Jarque–Bera", "< 0,0001" if row.jarque_bera_p < .0001 else fmt(row.jarque_bera_p, 4))
                c2.metric("p-valor Breusch–Pagan", "< 0,0001" if row.breusch_pagan_p < .0001 else fmt(row.breusch_pagan_p, 4))
                c3.metric("Média do erro no teste", fmt(row.media_erro_validacao))
                st.caption("Os testes avaliam resíduos do ajuste GAM no treino: normalidade (Jarque–Bera) e variância constante (Breusch–Pagan). Valores pequenos são evidência contra essas suposições. Isso limita inferência clássica sobre os coeficientes spline; não elimina o uso preditivo.")

        autocorr = get_data("autocorrelacao")
        if not autocorr.empty:
            autocorr = autocorr[(autocorr.target == target) & (autocorr.modelo == selected_model)]
            if "particao" in autocorr:
                autocorr = autocorr[autocorr.particao.eq("teste_reservado")]
        if not autocorr.empty:
            st.markdown("**Autocorrelação dos erros no teste reservado**")
            st.metric("Erro mensal lag-1 dentro da célula H3", fmt(autocorr.iloc[-1].autocorrelacao_erro_lag1, 3))
            st.caption("Valor perto de zero indica menos padrão temporal restante nos erros; este resultado é medido no conjunto reservado.")

        residual_shape = get_data("forma_residuo")
        if not residual_shape.empty:
            residual_shape = residual_shape[(residual_shape.target == target) & (residual_shape.modelo == selected_model)]
            if "particao" in residual_shape:
                residual_shape = residual_shape[residual_shape.particao.eq("teste_reservado")]
        if not residual_shape.empty and "DATA" in residual_shape:
            residual_shape["DATA"] = pd.to_datetime(residual_shape["DATA"])
            fig = px.line(residual_shape.sort_values("DATA"), x="DATA", y="residuo_medio", markers=True,
                          labels={"DATA": "Mês reservado", "residuo_medio": "Erro médio (observado − previsto)"})
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Erro mensal positivo indica subprevisão em média; negativo indica sobreprevisão.")


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

