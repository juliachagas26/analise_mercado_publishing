import streamlit as st
import plotly.express as px
import pandas as pd

from utils import (
    carregar_dados_consolidadores,
    calcular_variacoes,
    calcular_hhi_temporal,
    carregar_categoria_completa,
    filtrar_top_medias,
    calcular_variacoes_veiculos,
    calcular_share_grupos,
    contar_players_ativos,
    calcular_area_share_top_players,
    carregar_dados_dispersao,
    listar_midias_categoria,
    prever_audiencia_regressao_linear,
    avaliar_modelo_regressao_linear,
    resumir_modelo_regressao_linear,
    prever_audiencia_regressao_exogenas,
    resumir_modelo_regressao_exogenas,
    avaliar_modelo_regressao_exogenas,
    dataframe_para_excel_bytes,
    preparar_dataframe_exportacao,
    GROUP_SIZES
)

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard TCC - Audiência",
    layout="wide"
)

# =========================================================
# CSS GLOBAL
# =========================================================

st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] .stRadio > div {
        gap: 0.2rem;
    }

    section[data-testid="stSidebar"] .stRadio label {
        font-size: 22px;
        color: #6e6e6e;
        font-weight: 400;
        padding: 0.35rem 0;
    }

    section[data-testid="stSidebar"] .stRadio label:hover {
        color: #222222;
    }

    section[data-testid="stSidebar"] .stRadio [data-checked="true"] p {
        color: #111111 !important;
        font-weight: 500;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# HELPERS
# =========================================================

MAPA_CORES_CATEGORIAS = {
    "News": "#FF4B4B",
    "Entertainment": "#FFB618",
    "Sports": "#3CC01B",
    "Food": "#B3308B"
}


def style_variacao(val):
    if val > 0:
        return "color: #008000; font-weight: bold"
    elif val < 0:
        return "color: #FF0000; font-weight: bold"
    return "color: gray"


def render_download_excel(df, nome_arquivo: str, nome_aba: str, label: str, key: str):
    df_export = preparar_dataframe_exportacao(df)

    if df_export.empty:
        return

    excel_bytes = dataframe_para_excel_bytes(df_export, nome_aba=nome_aba)

    st.download_button(
        label=label,
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key
    )


# =========================================================
# SIDEBAR - NAVEGAÇÃO
# =========================================================

st.sidebar.markdown(
    """
    <style>
    .logo-wrap {
        text-align: center;
        padding: 2px 6px 34px 6px;
        margin-bottom: 18px;
    }

    .logo-title {
        font-size: 26px;
        font-weight: 800;
        line-height: 0.95;
        letter-spacing: -1px;
        font-family: Roboto, Open Sans, sans-serif;
    }

    .logo-market {
        color: #49aee9;
    }

    .logo-scope {
        color: #0b3f78;
    }

    .logo-subtitle {
        margin-top: 8px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: #7f9caf;
        font-family: Roboto, Open Sans, sans-serif;
        text-transform: uppercase;
        line-height: 1.25;
    }

    section[data-testid="stSidebar"] .categoria-wrap {
        margin-top: -14px;
        padding-top: 0;
    }
    </style>

    <div class="logo-wrap">
        <div class="logo-title">
            <span class="logo-market">Market</span><span class="logo-scope">Scope</span>
        </div>
        <div class="logo-subtitle">
            Digital Audience Intelligence
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

secao = st.sidebar.radio(
    "",
    [
        "Visão geral por categoria",
        "HHI",
        "Análise por categoria",
        "Share dos grupos",
        "Share dos líderes",
        "Dispersão",
        "Predição de audiência",
    ],
    label_visibility="collapsed"
)

categoria_selecionada = None
if secao in [
    "Análise por categoria",
    "Share dos grupos",
    "Share dos líderes",
    "Dispersão",
    "Predição de audiência",
]:
    st.sidebar.markdown('<div class="categoria-wrap">', unsafe_allow_html=True)
    categoria_selecionada = st.sidebar.selectbox(
        "Categoria",
        ["news", "entretenimento", "sports", "food"],
        key="sidebar_categoria"
    )

# =========================================================
# 1. VISÃO GERAL POR CATEGORIA
# =========================================================

if secao == "Visão geral por categoria":
    st.markdown("#### Usuários Únicos por categoria")

    df_final = carregar_dados_consolidadores("data/")

    if not df_final.empty:
        fig = px.line(
            df_final,
            x="Date",
            y="Total_Real",
            color="Categoria",
            color_discrete_map=MAPA_CORES_CATEGORIAS,
            markers=True,
            title="Evolução Mensal de Usuários Únicos por Categoria (Comscore)",
            labels={
                "Total_Real": "Visitantes Únicos",
                "Date": "Período",
                "Categoria": "Nicho"
            },
            template="plotly_white"
        )

        fig.update_layout(
            hovermode="x unified",
            legend_title_text="Categorias",
            yaxis_tickformat=","
        )

        st.plotly_chart(fig, use_container_width=True)
        render_download_excel(
            df_final,
            "visao_geral_categoria.xlsx",
            "visao_geral",
            "Download",
            "download_visao_geral"
        )

        st.markdown("#### Variação mensal e anual por categoria")

        datas_disponiveis = sorted(df_final["Date"].unique(), reverse=True)
        opcoes_datas = {d.strftime("%B / %Y"): d for d in datas_disponiveis}

        col1, col2 = st.columns([1, 2])
        with col1:
            mes_selecionado_str = st.selectbox(
                "Selecione o mês de referência:",
                options=list(opcoes_datas.keys()),
                key="sb_visao_geral"
            )

        data_ref = opcoes_datas[mes_selecionado_str]
        df_var = calcular_variacoes(df_final, data_ref)

        nome_coluna_audiencia = f"Audiência Total ({mes_selecionado_str})"
        df_var = df_var.rename(columns={"Audiência Total": nome_coluna_audiencia})

        st.dataframe(
            df_var.style.format({
                nome_coluna_audiencia: "{:,.0f}",
                "Variação MoM (%)": "{:+.2f}%",
                "Variação YoY (%)": "{:+.2f}%"
            }).map(style_variacao, subset=["Variação MoM (%)", "Variação YoY (%)"]),
            use_container_width=True
        )

        render_download_excel(
            df_var,
            f"variacoes_categoria_{mes_selecionado_str}.xlsx",
            "variacoes",
            "Download",
            "download_variacoes_categoria"
        )

    else:
        st.error("Arquivos não encontrados na pasta 'data/'.")

# =========================================================
# 2. HHI
# =========================================================

elif secao == "HHI":
    st.markdown("#### Índice de concentração de mercado (HHI)")

    df_hhi = calcular_hhi_temporal("data/")

    if not df_hhi.empty:
        fig_hhi = px.line(
            df_hhi,
            x="Data",
            y="HHI",
            color="Categoria",
            color_discrete_map=MAPA_CORES_CATEGORIAS,
            markers=True,
            title="Evolução do Índice Herfindahl-Hirschman (HHI)",
            labels={"HHI": "Índice HHI", "Data": "Período"},
            template="plotly_white"
        )

        fig_hhi.add_hline(
            y=1000,
            line_dash="dash",
            line_color="gray",
            annotation_text="Concentração Moderada (> 1000)",
            annotation_position="bottom left"
        )

        fig_hhi.add_hline(
            y=1800,
            line_dash="dash",
            line_color="gray",
            annotation_text="Alta Concentração (> 1800)",
            annotation_position="top left"
        )

        fig_hhi.update_layout(
            yaxis_range=[0, max(df_hhi["HHI"].max() + 500, 2000)],
            hovermode="x unified"
        )

        st.plotly_chart(fig_hhi, use_container_width=True)
        render_download_excel(
            df_hhi,
            "hhi_categoria.xlsx",
            "hhi",
            "Download",
            "download_hhi"
        )

        with st.expander("O que esses valores significam?"):
            st.markdown("""
                O **Índice Herfindahl-Hirschman (HHI)** é utilizado em análises antitruste para medir o grau de concentração em um mercado relevante.

                **Como é calculado?**

                O HHI é calculado com base no **somatório do quadrado das participações de mercado** ($s_i^2$) de todas as empresas de um dado mercado:
            """)

            st.latex(r"HHI = \sum_{i=1}^{n} s_i^2")

            st.markdown("""
                O índice pode chegar até **10.000 pontos**, valor que representa um **monopólio** (uma única empresa com 100% do mercado).

                ---

                **Classificação do Mercado:**

                * **Abaixo de 1000:** Mercado desconcentrado.
                * **1000 a 1800:** Mercado moderadamente concentrado.
                * **Acima de 1800:** Mercado altamente concentrado.

                ---

                **Fonte:** [CADE - Guia de Termos](https://vcde.cade.gov.br/cadethes/pt-BR/page/indiceherfindahlhirschman?clang=pt-br)
            """)
    else:
        st.warning("Não foi possível calcular o HHI com os dados disponíveis.")

# =========================================================
# BASES POR CATEGORIA
# =========================================================

elif secao in [
    "Análise por categoria",
    "Share dos grupos",
    "Share dos líderes",
    "Dispersão",
    "Predição de audiência",
]:
    df_categoria_completa = carregar_categoria_completa(categoria_selecionada)
    df_cat = filtrar_top_medias(df_categoria_completa, n=10)

    # =====================================================
    # 3. ANÁLISE POR CATEGORIA
    # =====================================================

    if secao == "Análise por categoria":
        st.markdown(f"#### Análise por categoria: {categoria_selecionada.capitalize()}")

        if not df_cat.empty:
            fig_cat = px.line(
                df_cat,
                x="Date",
                y="Total_Real",
                color="Media",
                markers=True,
                title=f"Evolução Mensal: Principais Veículos de {categoria_selecionada.capitalize()}",
                labels={"Total_Real": "Visitantes Únicos", "Date": "Período", "Media": "Veículo"},
                template="plotly_white"
            )

            fig_cat.update_layout(
                hovermode="x unified",
                yaxis_tickformat=",",
                legend_title_text="Veículos"
            )

            st.plotly_chart(fig_cat, use_container_width=True)
            render_download_excel(
                df_cat,
                f"analise_categoria_{categoria_selecionada}.xlsx",
                "analise_categoria",
                "Download",
                "download_analise_categoria"
            )

            st.markdown("#### Variação mensal e anual dos veículos")

            datas_cat = sorted(df_cat["Date"].unique(), reverse=True)
            opcoes_datas_cat = {d.strftime("%B / %Y"): d for d in datas_cat}

            col1, col2 = st.columns([1, 2])
            with col1:
                mes_tab_veiculo = st.selectbox(
                    "Selecione o mês de referência:",
                    options=list(opcoes_datas_cat.keys()),
                    key="sb_veiculos_tab"
                )

            data_ref_veiculo = opcoes_datas_cat[mes_tab_veiculo]
            df_var_veiculos = calcular_variacoes_veiculos(df_cat, data_ref_veiculo)

            col_audiencia = f"Audiência ({mes_tab_veiculo})"
            df_var_veiculos = df_var_veiculos.rename(columns={"Audiência Total": col_audiencia})

            st.dataframe(
                df_var_veiculos.style.format({
                    col_audiencia: "{:,.0f}",
                    "Variação MoM (%)": "{:+.2f}%",
                    "Variação YoY (%)": "{:+.2f}%"
                }).map(style_variacao, subset=["Variação MoM (%)", "Variação YoY (%)"]),
                use_container_width=True
            )

            render_download_excel(
                df_var_veiculos,
                f"variacoes_veiculos_{categoria_selecionada}_{mes_tab_veiculo}.xlsx",
                "variacoes_veiculos",
                "Download",
                "download_variacoes_veiculos"
            )
        else:
            st.warning(f"Não foi possível carregar os dados de {categoria_selecionada}.")

    # =====================================================
    # 4. SHARE DOS GRUPOS
    # =====================================================

    elif secao == "Share dos grupos":
        st.markdown(f"#### Share dos grupos - {categoria_selecionada.capitalize()}")

        df_share_grupos = calcular_share_grupos(df_categoria_completa, categoria_selecionada)

        if not df_share_grupos.empty:
            df_plot = df_share_grupos.melt(
                id_vars=["Date"],
                var_name="Grupo",
                value_name="Percentual"
            )

            top_x, next_y = GROUP_SIZES.get(categoria_selecionada, (5, 10))
            mapa_grupos = {
                f"Top {top_x} Players": "#1f77b4",
                f"Próximos {next_y} Players": "#ff7f0e",
                "Players Restantes": "#7f7f7f"
            }

            fig_share = px.line(
                df_plot,
                x="Date",
                y="Percentual",
                color="Grupo",
                title=f"Concentração de Share: {categoria_selecionada.capitalize()}",
                labels={"Percentual": "Share de audiência", "Date": "Período"},
                markers=True,
                template="plotly_white",
                color_discrete_map=mapa_grupos
            )

            fig_share.update_layout(
                yaxis_tickformat=".1%",
                hovermode="x unified"
            )

            st.plotly_chart(fig_share, use_container_width=True)
            render_download_excel(
                df_plot,
                f"share_grupos_{categoria_selecionada}.xlsx",
                "share_grupos",
                "Download",
                "download_share_grupos"
            )

            st.caption(
                "Metodologia: os grupos são fixos e definidos pela média histórica de share dos veículos na categoria completa."
            )
        else:
            st.warning("Não foi possível calcular o share dos grupos.")

        # ===================  CONTAGEM DE PLAYERS ======================

        st.divider()

        st.markdown(f"#### Total de veículos ativos - {categoria_selecionada.capitalize()}")

        df_contagem_real = contar_players_ativos(categoria_selecionada)        

        if not df_contagem_real.empty:
            fig_barra = px.bar(
                df_contagem_real,
                x='Date',
                y='Quantidade de Players',
                title=f"Total de Veículos com Audiência Ativa (>0) - {categoria_selecionada.capitalize()}",
                labels={'Quantidade de Players': 'Nº de Veículos', 'Date': 'Período'},
                template="plotly_white",
                text_auto=True
            )

            fig_barra.update_traces(marker_color='#004A88', opacity=0.8)
            st.plotly_chart(fig_barra, use_container_width=True)
        else:
            st.warning("Não foi possível calcular a quantidade de players ativos.")

    # =====================================================
    # 5. SHARE DOS LÍDERES
    # =====================================================

    elif secao == "Share dos líderes":
        st.markdown(f"#### Share dos líderes - {categoria_selecionada.capitalize()}")

        df_area = calcular_area_share_top_players(df_categoria_completa, categoria_selecionada)

        if not df_area.empty:
            fig_area = px.area(
                df_area,
                x="Date",
                y="share",
                color="Media",
                title=f"Evolução do Market Share: Líderes Individuais em {categoria_selecionada.capitalize()}",
                labels={"share": "Market Share (%)", "Date": "Período", "Media": "Veículo"},
                template="plotly_white",
                category_orders={
                    "Media": df_area.groupby("Media")["share"].mean().sort_values(ascending=False).index.tolist()
                }
            )

            fig_area.update_layout(
                yaxis_tickformat=".1%",
                yaxis_range=[0, 1],
                hovermode="x unified"
            )

            st.plotly_chart(fig_area, use_container_width=True)
            render_download_excel(
                df_area,
                f"share_lideres_{categoria_selecionada}.xlsx",
                "share_lideres",
                "Download",
                "download_share_lideres"
            )

            st.caption("Market share calculado sobre o total da categoria em cada mês.")
        else:
            st.warning("Não foi possível calcular o share dos líderes.")

    # =====================================================
    # 6. DISPERSÃO
    # =====================================================

    elif secao == "Dispersão":
        st.markdown(f"#### Matriz de Alcance vs. Engajamento Mensal ({categoria_selecionada.capitalize()})")

        df_disp_full = carregar_dados_dispersao(categoria_selecionada)

        if not df_disp_full.empty:
            datas_disponiveis = sorted(df_disp_full["Date"].unique(), reverse=True)
            opcoes_datas_disp = {d.strftime("%B / %Y"): d for d in datas_disponiveis}

            col1, col2 = st.columns([1, 2])
            with col1:
                mes_selecionado_str = st.selectbox(
                    "Selecione o mês de referência:",
                    options=list(opcoes_datas_disp.keys()),
                    key="sb_dispersao_mensal"
                )

            data_ref_scatter = opcoes_datas_disp[mes_selecionado_str]
            df_mes_plot = df_disp_full[df_disp_full["Date"] == data_ref_scatter]

            fig_disp = px.scatter(
                df_mes_plot,
                x="Usuarios_Scatter",
                y="Visitas_Scatter",
                color="Media",
                hover_name="Media",
                text="Media",
                title=f"Posicionamento de Mercado: {mes_selecionado_str}",
                labels={
                    "Usuarios_Scatter": "Usuários Únicos",
                    "Visitas_Scatter": "Total de Visitas"
                },
                template="plotly_white"
            )

            fig_disp.update_traces(
                marker=dict(size=14, opacity=0.8, line=dict(width=1, color="DarkSlateGrey")),
                textposition="top center"
            )

            fig_disp.update_layout(
                xaxis_tickformat=",",
                yaxis_tickformat=",",
                hovermode="closest",
                showlegend=False
            )

            st.plotly_chart(fig_disp, use_container_width=True)
            render_download_excel(
                df_mes_plot,
                f"dispersao_{categoria_selecionada}_{mes_selecionado_str}.xlsx",
                "dispersao",
                "Download",
                "download_dispersao"
            )

        else:
            st.warning(f"Não há dados disponíveis para gerar o gráfico de dispersão em {categoria_selecionada}.")

    # =====================================================
    # 7. PREDIÇÃO
    # =====================================================

    elif secao == "Predição de audiência":
        st.markdown(f"#### Predição de audiência - {categoria_selecionada.capitalize()}")

        midias_disponiveis = listar_midias_categoria(categoria_selecionada)

        if not midias_disponiveis:
            st.warning("Não há mídias disponíveis para essa categoria.")
        else:
            col1, col2 = st.columns([2, 1])

            with col1:
                media_selecionada = st.selectbox(
                    "Selecione a mídia",
                    midias_disponiveis,
                    key="sb_media_predicao"
                )

            with col2:
                meses_futuros = st.selectbox(
                    "Horizonte da previsão",
                    [3, 6, 9, 12],
                    index=1,
                    key="sb_horizonte_predicao"
                )


            st.markdown("Ambiente de modelos")

            st.caption(
                "É possível escolher os modelos de predição entre os disponíveis e instalar novos modelos"
            )

            if "modelos_instalados" not in st.session_state:
                st.session_state["modelos_instalados"] = {}

            serie_id = f"{categoria_selecionada}_{media_selecionada}"

            if serie_id not in st.session_state["modelos_instalados"]:
                st.session_state["modelos_instalados"][serie_id] = [
                    "Regressão linear simples",
                    "Regressão linear com exógenas"
                ]

            col_modelo1, col_modelo2 = st.columns([2, 1])

            with col_modelo1:
                modelo_novo = st.selectbox(
                    "Modelo disponível para instalação",
                    [
                        "SARIMA",
                        "Prophet",
                        "Random Forest",
                        "XGBoost"
                    ],
                    key=f"modelo_para_instalar_{serie_id}"
                )

            with col_modelo2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Instalar modelo", key=f"btn_instalar_modelo_{serie_id}"):
                    if modelo_novo not in st.session_state["modelos_instalados"][serie_id]:
                        st.session_state["modelos_instalados"][serie_id].append(modelo_novo)
                        st.success(f"Modelo '{modelo_novo}' adicionado ao ambiente da série.")
                    else:
                        st.info(f"O modelo '{modelo_novo}' já está instalado para essa série.")

            modelo_ativo = st.selectbox(
                "Modelo ativo",
                st.session_state["modelos_instalados"][serie_id],
                key=f"modelo_ativo_{serie_id}"
            )

            df_pred = pd.DataFrame()
            df_metricas = pd.DataFrame()
            df_coef = pd.DataFrame()
            caption_modelo = ""

            if modelo_ativo == "Regressão linear simples":
                df_pred = prever_audiencia_regressao_linear(
                    categoria_selecionada,
                    media_selecionada,
                    meses_futuros=meses_futuros
                )
                df_metricas = avaliar_modelo_regressao_linear(
                    categoria_selecionada,
                    media_selecionada
                )

                df_coef = resumir_modelo_regressao_linear(
                    categoria_selecionada,
                    media_selecionada
                )

                caption_modelo = (
                    "Modelo-base de regressão linear simples usando apenas tendência temporal."
                    "Útil como linha de base comparativa, mas limitado para capturar sazonalidade e choques específicos."
                )

            elif modelo_ativo == "Regressão linear com exógenas":
                df_pred = prever_audiencia_regressao_exogenas(
                    categoria_selecionada,
                    media_selecionada,
                    meses_futuros=meses_futuros
                )

                df_metricas = avaliar_modelo_regressao_exogenas(
                    categoria_selecionada,
                    media_selecionada
                )

                df_coef = resumir_modelo_regressao_exogenas(
                    categoria_selecionada,
                    media_selecionada
                )

                caption_modelo = (
                    "Modelo de regressão linear com tendência temporal e variáveis exógenas específicas da categoria. "
                    "A projeção deve ser interpretada como cenário-base, útil para capturar tendência e sazonalidade/eventos, "
                    "mas não como previsão causal definitiva."
                )

            else:
                st.info(
                    f"O modelo '{modelo_ativo}' está representado no framework como extensão futura. "
                    "Nesta versão do protótipo, apenas a regressão linear simples e a regressão linear com exógenas estão operacionais."
                )

            if df_pred.empty:
                st.warning("Não há dados suficientes para gerar a previsão dessa mídia.")
            else:
                fig_pred = px.line(
                    df_pred,
                    x="Date",
                    y="Total_Real",
                    color="tipo",
                    markers=True,
                    title=f"Série histórica, ajuste e previsão - {media_selecionada}",
                    labels={
                        "Date": "Período",
                        "Total_Real": "Usuários únicos",
                        "tipo": "Série"
                    },
                    template="plotly_white",
                    color_discrete_map={
                        "Histórico": "#1f77b4",
                        "Ajustado": "#2ca02c",
                        "Previsto": "#ff7f0e"
                    }
                )

                fig_pred.update_layout(
                    hovermode="x unified",
                    yaxis_tickformat=","
                )

                fig_pred.for_each_trace(
                    lambda trace: trace.update(line=dict(dash="dot"))
                    if trace.name == "Ajustado" else ()
                )

                fig_pred.for_each_trace(
                    lambda trace: trace.update(line=dict(dash="dash"))
                    if trace.name == "Previsto" else ()
                )

                st.plotly_chart(fig_pred, use_container_width=True)
                render_download_excel(
                    df_pred,
                    f"predicao_{categoria_selecionada}_{media_selecionada}.xlsx",
                    "predicao",
                    "Download",
                    "download_predicao"
                )

                st.caption(
                    "Modelo de regressão linear com tendência temporal e variáveis exógenas específicas da categoria. "
                    "A projeção deve ser interpretada como cenário-base, útil para capturar tendência e sazonalidade/eventos, "
                    "mas não como previsão causal definitiva."
                )

                with st.expander("Ver métricas e coeficientes do modelo"):
                    df_metricas = avaliar_modelo_regressao_exogenas(
                        categoria_selecionada,
                        media_selecionada
                    )

                    if not df_metricas.empty:
                        st.markdown("**Métricas do modelo**")
                        st.dataframe(
                            df_metricas.style.format({"Valor": "{:,.2f}"}),
                            use_container_width=True
                        )
                        render_download_excel(
                            df_metricas,
                            f"metricas_modelo_{categoria_selecionada}_{media_selecionada}.xlsx",
                            "metricas",
                            "Download",
                            "download_metricas_modelo"
                        )

                    df_coef = resumir_modelo_regressao_exogenas(
                        categoria_selecionada,
                        media_selecionada
                    )

                    if not df_coef.empty:
                        st.markdown("**Coeficientes do modelo**")
                        st.dataframe(
                            df_coef.style.format({"Coeficiente": "{:,.2f}"}),
                            use_container_width=True
                        )
                        render_download_excel(
                            df_coef,
                            f"coeficientes_modelo_{categoria_selecionada}_{media_selecionada}.xlsx",
                            "coeficientes",
                            "Download",
                            "download_coeficientes_modelo"
                        )

# =========================================================
# RODAPÉ
# =========================================================

st.divider()

st.markdown(
    """
    <style>
    .footer {
        font-size: 12px;
        color: gray;
        text-align: left;
    }
    </style>
    <div class="footer">
        <b>Fonte de dados:</b> Comscore - MyMetrix<br>
        <i>Análise gerada para fins acadêmicos - DEL | Escola Politécnica da UFRJ (2026)</i><br>
        <b>Júlia Chagas</b>
    </div>
    """,
    unsafe_allow_html=True
)