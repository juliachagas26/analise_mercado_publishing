import os
from datetime import datetime
import pandas as pd
import streamlit as st
import numpy as np
from sklearn.linear_model import LinearRegression
from io import BytesIO


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

def dataframe_para_excel_bytes(df: pd.DataFrame, nome_aba: str = "dados") -> bytes:
    """
    Converte um DataFrame em bytes de um arquivo Excel.
    Exporta apenas um DataFrame por arquivo.
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba[:31])

    return output.getvalue()


def preparar_dataframe_exportacao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que o DataFrame exportado não contenha index visual
    e esteja pronto para download.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    return df.copy().reset_index(drop=True)

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


# =========================================================
# PREDIÇÃO
# =========================================================

@st.cache_data
def listar_midias_categoria(nome_categoria: str) -> list[str]:
    df = carregar_categoria_completa(nome_categoria)

    if df.empty:
        return []

    return sorted(df['Media'].dropna().unique().tolist())


@st.cache_data
def carregar_serie_player(nome_categoria: str, media: str) -> pd.DataFrame:
    df = carregar_categoria_completa(nome_categoria)

    if df.empty:
        return pd.DataFrame()

    df_player = df[df['Media'] == media].copy()
    df_player = df_player.sort_values('Date').reset_index(drop=True)

    return df_player[['Date', 'Media', 'Total_Real']]


@st.cache_data
def prever_audiencia_regressao_linear(
    nome_categoria: str,
    media: str,
    meses_futuros: int = 6
) -> pd.DataFrame:
    """
    Gera previsão por regressão linear simples usando o tempo
    como variável explicativa.

    Retorna um dataframe com:
    - Date
    - Media
    - Total_Real
    - tipo ("Histórico", "Ajustado" ou "Previsto")
    """
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 3:
        return pd.DataFrame()

    df_player = df_player.copy().sort_values('Date').reset_index(drop=True)

    # Índice temporal simples: 0, 1, 2, ...
    df_player['t'] = np.arange(len(df_player))

    X = df_player[['t']]
    y = df_player['Total_Real']

    modelo = LinearRegression()
    modelo.fit(X, y)

    # histórico real
    df_hist = df_player[["Date", "Media", "Total_Real"]].copy()
    df_hist["tipo"] = "Histórico"

    # histórico ajustado
    df_fit = df_player[["Date", "Media"]].copy()
    df_fit["Total_Real"] = modelo.predict(X)
    df_fit["Total_Real"] = np.maximum(df_fit["Total_Real"], 0)
    df_fit["tipo"] = "Ajustado"

    # histórico ajustado não será mostrado como fitted, só usamos a previsão futura
    ultimo_t = df_player['t'].max()
    ultima_data = df_player['Date'].max()

    datas_futuras = pd.date_range(
        start=ultima_data + pd.offsets.MonthBegin(1),
        periods=meses_futuros,
        freq='MS'
    )

    t_futuro = np.arange(ultimo_t + 1, ultimo_t + 1 + meses_futuros).reshape(-1, 1)
    y_prev = modelo.predict(t_futuro)

    # evita previsão negativa
    y_prev = np.maximum(y_prev, 0)

    df_prev = pd.DataFrame({
        'Date': datas_futuras,
        'Media': media,
        'Total_Real': y_prev,
        'tipo': 'Previsto'
    })

    return pd.concat([df_hist, df_fit, df_prev], ignore_index=True)

@st.cache_data
def avaliar_modelo_regressao_linear(nome_categoria: str, media: str) -> pd.DataFrame:
    """
    Retorna métricas de ajuste da regressão linear simples.
    """
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 3:
        return pd.DataFrame()

    df = df_player.copy().sort_values("Date").reset_index(drop=True)
    df["t"] = np.arange(len(df))

    X = df[["t"]]
    y = df["Total_Real"]

    modelo = LinearRegression()
    modelo.fit(X, y)

    y_pred = modelo.predict(X)
    y_pred = np.maximum(y_pred, 0)

    mae = np.mean(np.abs(y - y_pred))
    y_safe = np.where(y == 0, np.nan, y)
    mape = np.nanmean(np.abs((y - y_pred) / y_safe)) * 100
    r2 = modelo.score(X, y)

    return pd.DataFrame({
        "Métrica": ["R²", "MAE", "MAPE (%)", "N observações"],
        "Valor": [r2, mae, mape, len(df)]
    })


@st.cache_data
def resumir_modelo_regressao_linear(nome_categoria: str, media: str) -> pd.DataFrame:
    """
    Retorna os coeficientes da regressão linear simples.
    """
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 3:
        return pd.DataFrame()

    df = df_player.copy().sort_values("Date").reset_index(drop=True)
    df["t"] = np.arange(len(df))

    X = df[["t"]]
    y = df["Total_Real"]

    modelo = LinearRegression()
    modelo.fit(X, y)

    return pd.DataFrame({
        "Variável": ["Intercepto", "t"],
        "Coeficiente": [modelo.intercept_, modelo.coef_[0]]
    })




@st.cache_data
def adicionar_exogenas_categoria(df: pd.DataFrame, categoria: str) -> pd.DataFrame:
    """
    Adiciona variáveis exógenas por categoria.

    Regras:
    - news: tendência + dummies mensais + eleição municipal/nacional
    - entretenimento: tendência + BBB
    - food: tendência + dummies mensais
    - sports: tendência + dummies mensais + olimpíadas + copa
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    categoria = str(categoria).lower().strip()

    df["ano"] = df["Date"].dt.year
    df["mes"] = df["Date"].dt.month

    # inicializa todas as colunas possíveis
    for i in range(1, 13):
        df[f"mes_{i}"] = 0

    df["eleicao_municipal"] = 0
    df["eleicao_nacional"] = 0
    df["bbb"] = 0
    df["olimpiadas"] = 0
    df["copa_fifa"] = 0

    # categorias que usam sazonalidade mensal no modelo
    if categoria in ["news", "sports", "food"] or categoria not in ["entretenimento"]:
        for i in range(1, 13):
            df.loc[df["mes"] == i, f"mes_{i}"] = 1

    if categoria == "news":
        anos_eleicao_nacional = {2018, 2022, 2026, 2030}
        anos_eleicao_municipal = {2016, 2020, 2024, 2028}

        df.loc[
            (df["ano"].isin(anos_eleicao_nacional)) & (df["mes"] == 10),
            "eleicao_nacional"
        ] = 1

        df.loc[
            (df["ano"].isin(anos_eleicao_municipal)) & (df["mes"] == 10),
            "eleicao_municipal"
        ] = 1

    elif categoria == "entretenimento":
        df.loc[df["mes"].isin([1, 2, 3, 4]), "bbb"] = 1


    elif categoria == "sports":
        anos_olimpiadas = {2016, 2021, 2024, 2028, 2032}
        anos_copa = {2018, 2022, 2026, 2030}

        df.loc[
            (df["ano"].isin(anos_olimpiadas)) & (df["mes"].isin([7, 8])),
            "olimpiadas"
        ] = 1

        df.loc[
            (df["ano"].isin(anos_copa)) & (df["mes"].isin([6, 7])),
            "copa_fifa"
        ] = 1

    return df

def obter_colunas_exogenas_por_categoria(categoria: str) -> list[str]:
    categoria = str(categoria).lower().strip()

    colunas_meses = [f"mes_{i}" for i in range(1, 12)]

    if categoria == "news":
        return colunas_meses + [
            "eleicao_municipal",
            "eleicao_nacional",
        ]

    elif categoria == "entretenimento":
        return ["bbb"]

    elif categoria == "food":
        return colunas_meses

    elif categoria == "sports":
        return colunas_meses + ["olimpiadas", "copa_fifa"]

    return colunas_meses


@st.cache_data
def prever_audiencia_regressao_exogenas(
    nome_categoria: str,
    media: str,
    meses_futuros: int = 6
) -> pd.DataFrame:
    """
    Previsão de audiência com regressão linear + exógenas.

    Usa:
    - tendência temporal (t)
    - dummies de mês
    - eventos exógenos da categoria

    Retorna um DataFrame com:
    - Date
    - Media
    - Total_Real
    - tipo: Histórico / Ajustado / Previsto
    """
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 6:
        return pd.DataFrame()

    df_player = df_player.copy().sort_values("Date").reset_index(drop=True)

    # histórico + exógenas
    df_hist = adicionar_exogenas_categoria(df_player, nome_categoria)
    df_hist["t"] = np.arange(len(df_hist))

    col_exog = obter_colunas_exogenas_por_categoria(nome_categoria)

    for col in col_exog:
        if col not in df_hist.columns:
            df_hist[col] = 0

    X_hist = df_hist[["t"] + col_exog]
    y_hist = df_hist["Total_Real"]

    modelo = LinearRegression()
    modelo.fit(X_hist, y_hist)

    # série histórica real
    df_hist_plot = df_hist[["Date", "Media", "Total_Real"]].copy()
    df_hist_plot["tipo"] = "Histórico"

    # série ajustada no histórico
    df_fit_plot = df_hist[["Date", "Media"]].copy()
    df_fit_plot["Total_Real"] = modelo.predict(X_hist)
    df_fit_plot["Total_Real"] = np.maximum(df_fit_plot["Total_Real"], 0)
    df_fit_plot["tipo"] = "Ajustado"

    # futuro
    ultima_data = df_hist["Date"].max()
    datas_futuras = pd.date_range(
        start=ultima_data + pd.offsets.MonthBegin(1),
        periods=meses_futuros,
        freq="MS"
    )

    df_fut = pd.DataFrame({
        "Date": datas_futuras,
        "Media": media
    })

    df_fut = adicionar_exogenas_categoria(df_fut, nome_categoria)
    df_fut["t"] = np.arange(len(df_hist), len(df_hist) + len(df_fut))

    for col in col_exog:
        if col not in df_fut.columns:
            df_fut[col] = 0

    X_fut = df_fut[["t"] + col_exog]
    y_fut = modelo.predict(X_fut)
    y_fut = np.maximum(y_fut, 0)

    df_prev_plot = df_fut[["Date", "Media"]].copy()
    df_prev_plot["Total_Real"] = y_fut
    df_prev_plot["tipo"] = "Previsto"

    df_saida = pd.concat(
        [df_hist_plot, df_fit_plot, df_prev_plot],
        ignore_index=True
    )

    return df_saida


@st.cache_data
def resumir_modelo_regressao_exogenas(nome_categoria: str, media: str) -> pd.DataFrame:
    """
    Retorna os coeficientes da regressão linear com exógenas.
    """
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 6:
        return pd.DataFrame()

    df = adicionar_exogenas_categoria(df_player, nome_categoria)
    df["t"] = np.arange(len(df))

    col_exog = obter_colunas_exogenas_por_categoria(nome_categoria)

    for col in col_exog:
        if col not in df.columns:
            df[col] = 0

    X = df[["t"] + col_exog]
    y = df["Total_Real"]

    modelo = LinearRegression()
    modelo.fit(X, y)

    coef_df = pd.DataFrame({
        "Variável": ["Intercepto"] + list(X.columns),
        "Coeficiente": [modelo.intercept_] + list(modelo.coef_)
    })

    return coef_df

@st.cache_data
def avaliar_modelo_regressao_exogenas(nome_categoria: str, media: str) -> pd.DataFrame:
    df_player = carregar_serie_player(nome_categoria, media)

    if df_player.empty or len(df_player) < 6:
        return pd.DataFrame()

    df = adicionar_exogenas_categoria(df_player, nome_categoria)
    df["t"] = np.arange(len(df))

    col_exog = obter_colunas_exogenas_por_categoria(nome_categoria)

    for col in col_exog:
        if col not in df.columns:
            df[col] = 0

    X = df[["t"] + col_exog]
    y = df["Total_Real"]

    modelo = LinearRegression()
    modelo.fit(X, y)

    y_pred = modelo.predict(X)
    y_pred = np.maximum(y_pred, 0)

    mae = np.mean(np.abs(y - y_pred))

    y_safe = np.where(y == 0, np.nan, y)
    mape = np.nanmean(np.abs((y - y_pred) / y_safe)) * 100

    r2 = modelo.score(X, y)

    return pd.DataFrame({
        "Métrica": ["R²", "MAE", "MAPE (%)", "N observações"],
        "Valor": [r2, mae, mape, len(df)]
    })