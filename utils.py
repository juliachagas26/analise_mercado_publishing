import os
from datetime import datetime

import pandas as pd
import streamlit as st


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

DATA_RULES = {
    'news': {
        'arquivo': 'news.xlsx',
        'filtro_total': 'News/Information',
        'label': 'News'
    },
    'entretenimento': {
        'arquivo': 'entretenimento.xlsx',
        'filtro_total': 'Entertainment - News',
        'label': 'Entertainment'
    },
    'sports': {
        'arquivo': 'sports.xlsx',
        'filtro_total': 'Sports',
        'label': 'Sports'
    },
    'food': {
        'arquivo': 'food.xlsx',
        'filtro_total': 'Lifestyles - Food',
        'label': 'Food'
    }
}

GROUP_SIZES = {
    'news': (10, 15),
    'entretenimento': (10, 10),
    'sports': (5, 7),
    'food': (5, 10)
}

MONTH_MAP = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4,
    'May': 5, 'June': 6, 'July': 7, 'August': 8,
    'September': 9, 'October': 10, 'November': 11, 'December': 12
}


# =========================================================
# HELPERS
# =========================================================

def _normalizar_categoria(nome_categoria: str) -> str:
    return str(nome_categoria).lower().strip()


def _obter_regra_categoria(nome_categoria: str):
    cat_key = _normalizar_categoria(nome_categoria)
    return DATA_RULES.get(cat_key), cat_key


def _detectar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    cols = [str(col).strip() for col in df.columns]
    for candidato in candidatos:
        for col in cols:
            if candidato.lower() in col.lower():
                return col
    return None


def _parse_date_series(df: pd.DataFrame) -> pd.Series:
    """
    Constrói coluna Date padronizada, aceitando mês numérico ou nome em inglês.
    """
    meses = df['Month'].astype(str).str.strip()

    mes_num = pd.to_numeric(meses, errors='coerce')

    if mes_num.isna().any():
        mes_num = meses.map(MONTH_MAP).fillna(mes_num)

    datas = pd.to_datetime(
        df['Year'].astype(int).astype(str) + '-' +
        mes_num.astype(int).astype(str).str.zfill(2) + '-01',
        errors='coerce'
    )
    return datas


def _encontrar_coluna_users(df: pd.DataFrame) -> str | None:
    """
    Prioriza explicitamente usuários únicos.
    """
    candidatos = [
        'Total Unique Visitors/Viewers',
        'Total Unique Visitors',
        'Unique Visitors/Viewers',
        'Unique Visitors'
    ]
    return _detectar_coluna(df, candidatos)


def _encontrar_coluna_visits(df: pd.DataFrame) -> str | None:
    """
    Prioriza explicitamente visits.
    """
    candidatos = [
        'Total Visits',
        'Visits'
    ]
    return _detectar_coluna(df, candidatos)


def _ajustar_escala_serie(serie: pd.Series, nome_coluna: str) -> pd.Series:
    """
    Se a coluna vier em milhares '(000)', converte para absoluto.
    Caso contrário, mantém.
    """
    fator = 1000 if '(000)' in str(nome_coluna) else 1
    return pd.to_numeric(serie, errors='coerce') * fator


@st.cache_data
def _ler_excel(caminho: str) -> pd.DataFrame:
    df = pd.read_excel(caminho)
    df.columns = [str(col).strip() for col in df.columns]
    return df


# =========================================================
# BASE CONSOLIDADA DAS CATEGORIAS
# =========================================================

@st.cache_data
def carregar_dados_consolidadores(diretorio_dados: str) -> pd.DataFrame:
    lista_frames = []

    for _, regra in DATA_RULES.items():
        caminho = os.path.join(diretorio_dados, regra['arquivo'])

        if not os.path.exists(caminho):
            continue

        df = _ler_excel(caminho).copy()
        df['Date'] = _parse_date_series(df)

        col_users = _encontrar_coluna_users(df)
        if col_users is None:
            continue

        df_categoria = df[df['Media'].astype(str).str.strip() == regra['filtro_total']].copy()
        df_categoria['Total_Real'] = _ajustar_escala_serie(df_categoria[col_users], col_users)
        df_categoria['Categoria'] = regra['label']

        lista_frames.append(df_categoria[['Date', 'Categoria', 'Total_Real']])

    if lista_frames:
        return pd.concat(lista_frames, ignore_index=True).sort_values(['Categoria', 'Date'])

    return pd.DataFrame()


@st.cache_data
def calcular_variacoes(df: pd.DataFrame, data_selecionada) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(['Categoria', 'Date'])

    df['MoM (%)'] = df.groupby('Categoria')['Total_Real'].pct_change(periods=1) * 100
    df['YoY (%)'] = df.groupby('Categoria')['Total_Real'].pct_change(periods=12) * 100

    df_filtrado = df[df['Date'] == data_selecionada].copy()

    tabela = df_filtrado[['Categoria', 'Total_Real', 'MoM (%)', 'YoY (%)']].copy()
    tabela.columns = ['Categoria', 'Audiência Total', 'Variação MoM (%)', 'Variação YoY (%)']

    return tabela.sort_values('Categoria')


# =========================================================
# HHI - FIXADO EM VISITS
# =========================================================

@st.cache_data
def calcular_hhi_temporal(diretorio_dados: str) -> pd.DataFrame:
    resultados = []

    for cat_key, regra in DATA_RULES.items():
        caminho = os.path.join(diretorio_dados, regra['arquivo'])
        if not os.path.exists(caminho):
            continue

        df = _ler_excel(caminho).copy()

        col_visits = _encontrar_coluna_visits(df)
        if col_visits is None:
            continue

        df['Date'] = _parse_date_series(df)

        df_limpo = df[df['Media'].astype(str).str.strip() != regra['filtro_total']].copy()
        df_limpo['Visits_Real'] = _ajustar_escala_serie(df_limpo[col_visits], col_visits)
        df_limpo = df_limpo.dropna(subset=['Date', 'Visits_Real'])

        for data, grupo in df_limpo.groupby('Date'):
            total_mes = grupo['Visits_Real'].sum()

            if total_mes <= 0:
                continue

            shares = (grupo['Visits_Real'] / total_mes) * 100
            hhi_mes = (shares ** 2).sum()

            resultados.append({
                'Data': data,
                'Categoria': regra['label'],
                'HHI': hhi_mes
            })

    if resultados:
        return pd.DataFrame(resultados).sort_values(['Categoria', 'Data'])

    return pd.DataFrame()


# =========================================================
# CATEGORIA COMPLETA E TOP PLAYERS
# =========================================================

@st.cache_data
def carregar_categoria_completa(nome_categoria: str, diretorio_dados: str = "data") -> pd.DataFrame:
    regra, cat_key = _obter_regra_categoria(nome_categoria)
    if regra is None:
        return pd.DataFrame()

    caminho = os.path.join(diretorio_dados, regra['arquivo'])
    if not os.path.exists(caminho):
        return pd.DataFrame()

    df = _ler_excel(caminho).copy()
    df['Date'] = _parse_date_series(df)

    col_users = _encontrar_coluna_users(df)
    col_visits = _encontrar_coluna_visits(df)

    if col_users is None:
        return pd.DataFrame()

    df = df[df['Media'].astype(str).str.strip() != regra['filtro_total']].copy()

    df['Total_Real'] = _ajustar_escala_serie(df[col_users], col_users)

    if col_visits is not None:
        df['Visits_Real'] = _ajustar_escala_serie(df[col_visits], col_visits)
    else:
        df['Visits_Real'] = pd.NA

    df = df.dropna(subset=['Date', 'Total_Real'])

    cols_saida = ['Date', 'Media', 'Total_Real', 'Visits_Real', 'Year', 'Month']
    cols_saida = [c for c in cols_saida if c in df.columns]

    return df[cols_saida].sort_values(['Date', 'Media']).reset_index(drop=True)


@st.cache_data
def filtrar_top_medias(df_categoria_completa: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if df_categoria_completa.empty:
        return pd.DataFrame()

    df = df_categoria_completa.copy()

    top_medias = (
        df.groupby('Media')['Total_Real']
        .mean()
        .nlargest(n)
        .index
    )

    df_top = df[df['Media'].isin(top_medias)].copy()
    return df_top.sort_values(['Date', 'Media']).reset_index(drop=True)


@st.cache_data
def carregar_detalhes_categoria(nome_categoria: str) -> pd.DataFrame:
    """
    Mantida para compatibilidade com o app atual.
    Agora:
    - carrega a base completa da categoria
    - depois filtra Top 10 histórico
    """
    df_completo = carregar_categoria_completa(nome_categoria)
    return filtrar_top_medias(df_completo, n=10)


# =========================================================
# VARIAÇÕES POR VEÍCULO
# =========================================================

@st.cache_data
def calcular_variacoes_veiculos(df_detalhado: pd.DataFrame, data_selecionada) -> pd.DataFrame:
    if df_detalhado.empty:
        return pd.DataFrame()

    df = df_detalhado.copy()
    df = df.sort_values(['Media', 'Date'])

    df['MoM (%)'] = df.groupby('Media')['Total_Real'].pct_change(periods=1) * 100
    df['YoY (%)'] = df.groupby('Media')['Total_Real'].pct_change(periods=12) * 100

    df_mes = df[df['Date'] == data_selecionada].copy()
    tabela_top10 = df_mes.nlargest(10, 'Total_Real')

    tabela = tabela_top10[['Media', 'Total_Real', 'MoM (%)', 'YoY (%)']].copy()
    tabela.columns = ['Veículo', 'Audiência Total', 'Variação MoM (%)', 'Variação YoY (%)']

    return tabela.reset_index(drop=True)


# =========================================================
# SHARE DOS GRUPOS - BASE COMPLETA
# =========================================================

@st.cache_data
def calcular_share_grupos(df_categoria_completa: pd.DataFrame, nome_categoria: str) -> pd.DataFrame:
    if df_categoria_completa.empty:
        return pd.DataFrame()

    cat_key = _normalizar_categoria(nome_categoria)
    top_x, next_y = GROUP_SIZES.get(cat_key, (5, 10))

    df = df_categoria_completa.copy()

    df['Mensal_Total'] = df.groupby('Date')['Total_Real'].transform('sum')
    df = df[df['Mensal_Total'] > 0].copy()
    df['share'] = df['Total_Real'] / df['Mensal_Total']

    media_rank = (
        df.groupby('Media')['share']
        .mean()
        .sort_values(ascending=False)
    )

    group1_players = media_rank.head(top_x).index.tolist()
    group2_players = media_rank.iloc[top_x:top_x + next_y].index.tolist()

    resultados = []
    for data, gp in df.groupby('Date'):
        s1 = gp.loc[gp['Media'].isin(group1_players), 'share'].sum()
        s2 = gp.loc[gp['Media'].isin(group2_players), 'share'].sum()
        s3 = max(0.0, 1.0 - s1 - s2)

        resultados.append({
            'Date': data,
            f'Top {top_x} Players': s1,
            f'Próximos {next_y} Players': s2,
            'Players Restantes': s3
        })

    return pd.DataFrame(resultados).sort_values('Date').reset_index(drop=True)


# =========================================================
# CONTAGEM DE PLAYERS ATIVOS
# =========================================================

@st.cache_data
def contar_players_ativos(nome_categoria: str) -> pd.DataFrame:
    df_completo = carregar_categoria_completa(nome_categoria)

    if df_completo.empty:
        return pd.DataFrame()

    df = df_completo.copy()
    df = df[df['Total_Real'] > 0].copy()

    contagem = df.groupby('Date')['Media'].nunique().reset_index()
    contagem.columns = ['Date', 'Quantidade de Players']

    return contagem.sort_values('Date').reset_index(drop=True)


# =========================================================
# ÁREA DE SHARE DOS TOP PLAYERS - BASE COMPLETA
# =========================================================

@st.cache_data
def calcular_area_share_top_players(df_categoria_completa: pd.DataFrame, nome_categoria: str) -> pd.DataFrame:
    if df_categoria_completa.empty:
        return pd.DataFrame()

    cat_key = _normalizar_categoria(nome_categoria)
    top_x, _ = GROUP_SIZES.get(cat_key, (5, 10))

    df = df_categoria_completa.copy()

    df['Mensal_Total'] = df.groupby('Date')['Total_Real'].transform('sum')
    df = df[df['Mensal_Total'] > 0].copy()
    df['share'] = df['Total_Real'] / df['Mensal_Total']

    top_players = (
        df.groupby('Media')['share']
        .mean()
        .nlargest(top_x)
        .index.tolist()
    )

    df_top_plot = df[df['Media'].isin(top_players)].copy()

    return df_top_plot.sort_values(['Date', 'share'], ascending=[True, False]).reset_index(drop=True)


# =========================================================
# DISPERSÃO
# =========================================================

@st.cache_data
def carregar_dados_dispersao(nome_categoria: str) -> pd.DataFrame:
    df = carregar_categoria_completa(nome_categoria)

    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Usuarios_Scatter: Total_Real já está em absoluto
    df['Usuarios_Scatter'] = pd.to_numeric(df['Total_Real'], errors='coerce')

    # Visitas_Scatter: Visits_Real já está em absoluto, se existir
    df['Visitas_Scatter'] = pd.to_numeric(df['Visits_Real'], errors='coerce')

    return df.dropna(subset=['Date', 'Media', 'Usuarios_Scatter', 'Visitas_Scatter']).reset_index(drop=True)
