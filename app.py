import streamlit as st
import pandas as pd
import plotly.express as px
import os
from utils import (
    carregar_dados_consolidadores, 
    calcular_variacoes, 
    calcular_hhi_temporal, 
    carregar_detalhes_categoria, 
    calcular_variacoes_veiculos, 
    calcular_share_grupos,
    contar_players_ativos,
    calcular_area_share_top_players,
    carregar_dados_dispersao
)


st.set_page_config(page_title="Dashboard TCC - Audiência", layout="wide")

st.title("Análise de Audiência Publishing Digital")

#USUÁRIOS ÚNICOS POR CATEGORIA - SERIE TEMPORAL

# 1. Obter os dados processados
df_final = carregar_dados_consolidadores("data/")

st.markdown("""

            <h4>Usuários Únicos por categoria</h4>

            """, 
            unsafe_allow_html=True)

if not df_final.empty:

    mapa_cores = {
    'News': '#FF4B4B',
    'Entertainment': "#FFB618",
    'Sports': "#3CC01B",   
    'Food': "#B3308B"
    }

    # gráfico de linha temporal para cada categoria
    fig = px.line(
        df_final, 
        x='Date', 
        y='Total_Real', 
        color='Categoria',
        color_discrete_map=mapa_cores,
        markers=True, # Adiciona os pontos nas linhas como no print
        title="Evolução Mensal de Usuários Únicos por Categoria (Comscore)",
        labels={
            "Total_Real": "Visitantes Únicos",
            "Date": "Período",
            "Categoria": "Nicho"
        },
        template="plotly_white" # Deixa o fundo limpo
    )

    # 3. Ajustes de layout para ficar idêntico
    fig.update_layout(
        hovermode="x unified",
        legend_title_text='Categorias',
        yaxis_tickformat=',', # Adiciona separador de milhar
    )

    # Exibir no Streamlit
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Arquivos não encontrados na pasta 'data/'. Verifique os nomes dos arquivos Excel.")


try:
    # 1. Carregar dados brutos
    df_final = carregar_dados_consolidadores("data/")
    
    # 2. Criar lista de meses disponíveis (ordenada do mais recente para o mais antigo)
    datas_disponiveis = sorted(df_final['Date'].unique(), reverse=True)
    
    # Criar um dicionário para exibir "Abril / 2026" no selectbox, mas manter o objeto Date por trás
    opcoes_datas = {d.strftime('%B / %Y'): d for d in datas_disponiveis}
    
    # 3. Selectbox para o usuário escolher o mês
    col1, col2 = st.columns([1, 2])
    with col1: 
        mes_selecionado_str = st.selectbox("Selecione o mês de referência:", 
                                           options=list(opcoes_datas.keys()))
    data_ref = opcoes_datas[mes_selecionado_str]
    
    # 4. Calcular variações para a data escolhida
    df_var = calcular_variacoes(df_final, data_ref)
    
    # 5. Renomear coluna com o mês escolhido
    nome_coluna_audiencia = f"Audiência Total ({mes_selecionado_str})"
    df_var = df_var.rename(columns={'Audiência Total': nome_coluna_audiencia})

    def color_variacao(val):
        if val > 0: return 'color: #008000; font-weight: bold'
        elif val < 0: return 'color: #FF0000; font-weight: bold'
        return 'color: gray'

    # 6. Exibir a Tabela
    st.dataframe(
        df_var.style.format({
            nome_coluna_audiencia: '{:,.0f}',
            'Variação MoM (%)': '{:+.2f}%',
            'Variação YoY (%)': '{:+.2f}%'
        }).map(color_variacao, subset=['Variação MoM (%)', 'Variação YoY (%)']),
        use_container_width=True
    )

except Exception as e:
    st.error(f"Erro ao carregar o seletor de meses: {e}")


# CONCENTRAÇÃO DE MERCADO

st.divider()

st.markdown("""

            <h4>Índice de concentração de mercado (HHI)</h4>

            """, 
            unsafe_allow_html=True)


try:
    # 1. Obter dados do HHI
    df_hhi = calcular_hhi_temporal("data/")
    
    
    
    if not df_hhi.empty:

        mapa_cores = {
        'News': '#FF4B4B',
        'Entertainment': "#FFB618",
        'Sports': "#3CC01B",   
        'Food': "#B3308B"
        }
        # 2. Gerar Gráfico de Linha
        fig_hhi = px.line(
            df_hhi, 
            x='Data', 
            y='HHI', 
            color='Categoria',
            color_discrete_map=mapa_cores,
            markers=True,
            title="Evolução do Índice Herfindahl-Hirschman (HHI)",
            labels={'HHI': 'Índice HHI', 'Data': 'Período'},
            template="plotly_white"
        )

        # 3. Adicionar Linhas de Referência (Linhas Horizontais)
        fig_hhi.add_hline(y=1000, line_dash="dash", line_color="gray", 
                          annotation_text="Concentração Moderada (> 1000)", 
                          annotation_position="bottom left")
        
        fig_hhi.add_hline(y=1800, line_dash="dash", line_color="gray", 
                          annotation_text="Alta Concentração (> 1800)", 
                          annotation_position="top left")

        # 4. Ajustes de Layout
        fig_hhi.update_layout(
            yaxis_range=[0, max(df_hhi['HHI'].max() + 500, 2000)], # Garante que as linhas apareçam
            hovermode="x unified"
        )

        st.plotly_chart(fig_hhi, use_container_width=True)

        # 5. Texto de apoio para a banca do TCC
        with st.expander("O que esses valores significam?"):
            st.write("""
            O **HHI** varia de 0 a 10.000:
            - **Abaixo de 1000:** Mercado desconcentrado.
            - **1000 a 1800:** Mercado moderadamente concentrado.
            - **Acima de 1800:** Mercado altamente concentrado.
            """)
            
except Exception as e:
    st.error(f"Erro ao processar gráfico de HHI: {e}")



# ANALISE POR CATEGORIA

st.divider()

st.markdown("""

            <h4>Análise por categoria</h4>

            """, 
            unsafe_allow_html=True)


# 1. Escolha da Categoria
col1, col2 = st.columns([1, 2])
with col1: 
    categoria_selecionada = st.selectbox(
    "Selecione a categoria para ver os veículos individuais:",
    ["news", "entretenimento", "sports", "food"]
)

# 2. Carregar dados específicos (sem o totalizador)
df_cat = carregar_detalhes_categoria(categoria_selecionada)

if not df_cat.empty:
    # 3. Gráfico de Linha para os veículos daquela categoria
    fig_cat = px.line(
        df_cat, 
        x='Date', 
        y='Total_Real', 
        color='Media', 
        markers=True,
        title=f"Evolução Mensal: Principais Veículos de {categoria_selecionada.capitalize()}",
        labels={"Total_Real": "Visitantes Únicos", "Date": "Período", "Media": "Veículo"},
        template="plotly_white"
    )

    fig_cat.update_layout(
        hovermode="x unified",
        yaxis_tickformat=',',
        legend_title_text='Veículos'
    )

    st.plotly_chart(fig_cat, use_container_width=True)
else:
    st.error(f"Não foi possível carregar os detalhes da categoria {categoria_selecionada}.")



try:
    # 1. Pegar as datas disponíveis para esta categoria específica
    datas_cat = sorted(df_cat['Date'].unique(), reverse=True)
    opcoes_datas_cat = {d.strftime('%B / %Y'): d for d in datas_cat}
    
    # 2. Seletor de data específico para a tabela de veículos
    col1, col2 = st.columns([1, 2])
    with col1: 
        mes_tab_veiculo = st.selectbox(
        "Selecione o mês de referência:",
        options=list(opcoes_datas_cat.keys()),
        key="sb_veiculos_tab"
    )
    data_ref_veiculo = opcoes_datas_cat[mes_tab_veiculo]
    
    # 3. Calcular variações usando a nova função
    df_var_veiculos = calcular_variacoes_veiculos(df_cat, data_ref_veiculo)
    
    # 4. Nome dinâmico da coluna
    col_audiencia = f"Audiência ({mes_tab_veiculo})"
    df_var_veiculos = df_var_veiculos.rename(columns={'Audiência Total': col_audiencia})

    # 5. Formatação Visual
    def style_performance(val):
        if val > 0: return 'color: #008000; font-weight: bold'
        elif val < 0: return 'color: #FF0000; font-weight: bold'
        return 'color: gray'

    st.dataframe(
        df_var_veiculos.style.format({
            col_audiencia: '{:,.0f}',
            'Variação MoM (%)': '{:+.2f}%',
            'Variação YoY (%)': '{:+.2f}%'
        }).map(style_performance, subset=['Variação MoM (%)', 'Variação YoY (%)']),
        use_container_width=True
    )

except Exception as e:
    st.error(f"Erro ao calcular variações dos veículos: {e}")


# SHARES DOS GRUPOS


# 1. Calcular os dados de share usando a função do utils
df_share_grupos = calcular_share_grupos(df_cat, categoria_selecionada)

if not df_share_grupos.empty:
    # 2. Transformar para formato longo (melt) para o Plotly
    df_plot = df_share_grupos.melt(
        id_vars=['Date'], 
        var_name='Grupo', 
        value_name='Percentual'
    )

    # 3. Gerar o gráfico de linha
    fig_share = px.line(
        df_plot, 
        x='Date', 
        y='Percentual', 
        color='Grupo',
        title=f"Concentração de Share: {categoria_selecionada.capitalize()}",
        labels={'Percentual': 'Share de Visitas', 'Date': 'Período'},
        markers=True,
        template="plotly_white",
        # Cores fixas para os grupos para facilitar a leitura
        color_discrete_map={
            df_plot['Grupo'].unique()[0]: '#1f77b4', # Top (Azul)
            df_plot['Grupo'].unique()[1]: '#ff7f0e', # Meio (Laranja)
            df_plot['Grupo'].unique()[2]: '#7f7f7f'  # Restante (Cinza)
        }
    )

    # 4. Formatação do Eixo Y em Porcentagem
    fig_share.update_layout(
        yaxis_tickformat='.1%',
        hovermode="x unified"
    )

    st.plotly_chart(fig_share, use_container_width=True)
    
    st.caption(f"""
    **Metodologia:** Os grupos são fixos. Identificamos os veículos com a maior média histórica de audiência 
    e acompanhamos como a fatia de mercado desse grupo específico oscilou mês a mês.
    """)

# GRÁFICO DE BARRAS COM CONTAGEM DE PLAYERS

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
    
    fig_barra.update_traces(marker_color='#004A88', opacity=0.8) # Azul UFRJ
    st.plotly_chart(fig_barra, use_container_width=True)




df_area = calcular_area_share_top_players(df_cat, categoria_selecionada)

if not df_area.empty:
    fig_area = px.area(
        df_area, 
        x='Date', 
        y='share', 
        color='Media',
        title=f"Evolução do Market Share: Líderes Individuais em {categoria_selecionada.capitalize()} (Top {df_area['Media'].nunique()} Players)",
        labels={'share': 'Market Share (%)', 'Date': 'Período', 'Media': 'Veículo'},
        template="plotly_white",
        # Ordena para os maiores ficarem na base da pilha
        category_orders={"Media": df_area.groupby('Media')['share'].mean().sort_values(ascending=False).index.tolist()}
    )

    fig_area.update_layout(
        yaxis_tickformat='.1%',
        yaxis_range=[0, 1], # Força o eixo Y a ir até 100% para mostrar o vazio
        hovermode="x unified"
    )

    st.plotly_chart(fig_area, use_container_width=True)
    
    st.caption(f"""
    Conta de market share considerando o total de visitas
    """)

st.divider()
st.markdown(f"#### 🎯 Matriz de Alcance vs. Engajamento Mensal ({categoria_selecionada.capitalize()})")

# 1. Carregar todos os dados da categoria (já processados com escalas no utils)
df_disp_full = carregar_dados_dispersao(categoria_selecionada)

if not df_disp_full.empty:
    # 2. Criar o dicionário de datas (mesmo padrão das outras seções)
    # Ordenado do mais recente para o mais antigo
    datas_disponiveis = sorted(df_disp_full['Date'].unique(), reverse=True)
    opcoes_datas_disp = {d.strftime('%B / %Y'): d for d in datas_disponiveis}
    
    # 3. Selectbox usando a estrutura de colunas que você solicitou
    col1, col2 = st.columns([1, 2])
    with col1:
        mes_selecionado_str = st.selectbox(
            "Selecione o mês de referência:", 
            options=list(opcoes_datas_disp.keys()),
            key="sb_dispersao_mensal" # Chave única para não conflitar com outros selectboxes
        )
    
    # Define a data de referência baseada na chave escolhida
    data_ref_scatter = opcoes_datas_disp[mes_selecionado_str]
    
    # 4. Filtrar o DataFrame pelo objeto de data selecionado
    df_mes_plot = df_disp_full[df_disp_full['Date'] == data_ref_scatter]

    # 5. Gerar o Gráfico de Dispersão
    fig_disp = px.scatter(
        df_mes_plot,
        x='Usuarios_Scatter',
        y='Visitas_Scatter',
        color='Media',
        hover_name='Media',
        text='Media', # Exibe o nome do veículo ao lado do ponto
        title=f"Posicionamento de Mercado: {mes_selecionado_str}",
        labels={
            'Usuarios_Scatter': 'Usuários Únicos (Escala: Milhões)',
            'Visitas_Scatter': 'Total de Visitas (Escala: Milhares)'
        },
        template="plotly_white"
    )
    
    # Ajustes finos de visualização
    fig_disp.update_traces(
        marker=dict(size=14, opacity=0.8, line=dict(width=1, color='DarkSlateGrey')),
        textposition='top center'
    )
    
    fig_disp.update_layout(
        xaxis_tickformat=',',
        yaxis_tickformat=',',
        hovermode="closest",
        showlegend=False # Nomes já aparecem no gráfico e no hover
    )

    st.plotly_chart(fig_disp, use_container_width=True)

else:
    st.warning(f"Não há dados disponíveis para gerar o gráfico de dispersão em {categoria_selecionada}.")


# RODAPÉ
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