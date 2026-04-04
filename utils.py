import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime


def carregar_dados_consolidadores(diretorio_dados):
    # Linhas consolidadoras de cada categoria
    data_rules = {
        'News': ('news.xlsx', 'News/Information'),
        'Entertainment': ('entretenimento.xlsx', 'Entertainment - News'),
        'Sports': ('sports.xlsx', 'Sports'),
        'Food': ('food.xlsx', 'Lifestyles - Food')
    }
    

    lista_frames = []

    for label, (arquivo, entidade_mestre) in data_rules.items():
        caminho = os.path.join(diretorio_dados, arquivo)
        
        if os.path.exists(caminho):
            df = pd.read_excel(caminho)
            
            # --- Preparação da Data (Lógica do seu Colab) ---
            df['Date_Str'] = df['Year'].astype(str) + ' ' + df['Month'].astype(str).str.zfill(2)
            df['Date'] = pd.to_datetime(df['Date_Str'], format='%Y %m')
            
            # --- Filtro da Linha Agregadora ---
            # Filtramos apenas a linha que representa a categoria cheia
            df_categoria = df[df['Media'] == entidade_mestre].copy()
            
            metrica_original = 'Total Unique Visitors/Viewers (000)'
            df_categoria['Total_Real'] = df_categoria[metrica_original] * 1000
            
            # Adicionamos o nome da categoria para a legenda
            df_categoria['Categoria'] = label
            
            # Selecionamos apenas o necessário
            lista_frames.append(df_categoria[['Date', 'Categoria', 'Total_Real']])
    
    if lista_frames:
        return pd.concat(lista_frames, ignore_index=True)
    return pd.DataFrame()

@st.cache_data
def calcular_variacoes(df, data_selecionada):
    # Garante a ordem cronológica para o cálculo do pct_change
    df = df.sort_values(['Categoria', 'Date'])
    
    # Cálculos de MoM e YoY (feitos na base toda para não perder a referência)
    df['MoM (%)'] = df.groupby('Categoria')['Total_Real'].pct_change(periods=1) * 100
    df['YoY (%)'] = df.groupby('Categoria')['Total_Real'].pct_change(periods=12) * 100
    
    # Agora filtramos apenas pela data que o usuário escolheu no selectbox
    df_filtrado = df[df['Date'] == data_selecionada].copy()
    
    tabela = df_filtrado[['Categoria', 'Total_Real', 'MoM (%)', 'YoY (%)']]
    tabela.columns = ['Categoria', 'Audiência Total', 'Variação MoM (%)', 'Variação YoY (%)']
    
    return tabela



def calcular_hhi_temporal(diretorio_dados):
    data_rules = {
        'News': ('news.xlsx', 'News/Information'),
        'Entertainment': ('entretenimento.xlsx', 'Entertainment - News'),
        'Sports': ('sports.xlsx', 'Sports'),
        'Food': ('food.xlsx', 'Lifestyles - Food'),
        'Retail': ('retail.xlsx', 'Retail')
    }
    
    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    
    all_results = []

    for category, (file_path, filter_value) in data_rules.items():
        caminho = os.path.join(diretorio_dados, file_path)
        if os.path.exists(caminho):
            # Lendo o Excel e limpando nomes de colunas
            df = pd.read_excel(caminho)
            df.columns = [str(col).strip() for col in df.columns]
            
            # Identificar a métrica correta (Visits ou Visitors)
            col_metrica = None
            for c in df.columns:
                if 'Total Visits' in c or 'Total Unique Visitors' in c:
                    col_metrica = c
                    break
            
            if not col_metrica:
                continue

            # 1. Filtro da Entidade Mestre
            # Removemos a linha que contém o total da categoria para calcular o market share real
            df_filtered = df[df['Media'].astype(str).str.strip() != filter_value].copy()
            
            # Garante que a métrica é numérica
            df_filtered[col_metrica] = pd.to_numeric(df_filtered[col_metrica], errors='coerce')
            df_filtered = df_filtered.dropna(subset=[col_metrica])
            
            # 2. Agrupamento e Cálculo de HHI
            for (year, month), group in df_filtered.groupby(['Year', 'Month'], sort=False):
                # Views absolutas
                fator = 1000 if '(000)' in col_metrica else 1
                valor_absoluto = group[col_metrica] * fator
                total_mes = valor_absoluto.sum()
                
                if total_mes > 0:
                    shares = (valor_absoluto / total_mes) * 100
                    hhi_mes = (shares ** 2).sum()
                    
                    try:
                        # Se o mês já for um número (1, 2...), usamos direto
                        if str(month).isdigit():
                            mes_num = int(month)
                        else:
                            # Se for nome (January...), limpamos e buscamos no mapa
                            mes_limpo = str(month).strip()
                            mes_num = month_map.get(mes_limpo, 1) # Padrão 1 se não achar
                        
                        data_obj = datetime(int(year), mes_num, 1)
                        
                        all_results.append({
                            'Data': data_obj,
                            'Categoria': category,
                            'HHI': hhi_mes
                        })
                    except Exception:
                        continue
                    
    return pd.DataFrame(all_results)

@st.cache_data
def carregar_detalhes_categoria(nome_categoria):
    nome_categoria = nome_categoria.lower().strip()
    
    data_rules = {
        'news': ('news.xlsx', 'News/Information'),
        'entretenimento': ('entretenimento.xlsx', 'Entertainment - News'),
        'sports': ('sports.xlsx', 'Sports'),
        'food': ('food.xlsx', 'Lifestyles - Food')
    }
    
    if nome_categoria not in data_rules:
        return pd.DataFrame()
        
    arquivo, filtro_total = data_rules[nome_categoria]
    caminho = f"data/{arquivo}"
    
    if os.path.exists(caminho):
        df = pd.read_excel(caminho)
        df.columns = [str(col).strip() for col in df.columns]
        
        # 1. Filtro: Exclui a linha de soma (entidade mestre)
        df_detalhado = df[df['Media'].astype(str).str.strip() != filtro_total].copy()
        
        # 2. Preparação da Data e Métrica
        df_detalhado['Date_Str'] = df_detalhado['Year'].astype(str) + ' ' + df_detalhado['Month'].astype(str).str.zfill(2)
        df_detalhado['Date'] = pd.to_datetime(df_detalhado['Date_Str'], format='%Y %m')
        
        col_metrica = 'Total Unique Visitors/Viewers (000)'
        df_detalhado['Total_Real'] = pd.to_numeric(df_detalhado[col_metrica], errors='coerce') * 1000
        df_detalhado = df_detalhado.dropna(subset=['Total_Real'])

        # --- TRAVA DE TOP 10 ---
        # Calculamos a média de audiência de cada mídia para identificar os líderes
        top_10_medias = (
            df_detalhado.groupby('Media')['Total_Real']
            .mean()
            .nlargest(10)
            .index
        )
        
        # Filtramos o DataFrame original para manter apenas esses 10 players
        df_top_10 = df_detalhado[df_detalhado['Media'].isin(top_10_medias)]
        
        return df_top_10.sort_values('Date')
        
    return pd.DataFrame()

@st.cache_data
def calcular_variacoes_veiculos(df_detalhado, data_selecionada):
    # 1. Garantir ordem cronológica por veículo para o cálculo de variação
    df = df_detalhado.sort_values(['Media', 'Date'])
    
    # 2. Calcular variações agrupando por Media
    # Isso garante que o MoM do 'Site A' seja comparado com o 'Site A' do mês anterior
    df['MoM (%)'] = df.groupby('Media')['Total_Real'].pct_change(periods=1) * 100
    df['YoY (%)'] = df.groupby('Media')['Total_Real'].pct_change(periods=12) * 100
    
    # 3. Filtrar pelo mês escolhido
    df_mes = df[df['Date'] == data_selecionada].copy()
    
    # 4. Pegar os Top 10 pela Audiência Total do mês escolhido
    tabela_top10 = df_mes.nlargest(10, 'Total_Real')
    
    # 5. Organizar colunas
    tabela = tabela_top10[['Media', 'Total_Real', 'MoM (%)', 'YoY (%)']]
    tabela.columns = ['Veículo', 'Audiência Total', 'Variação MoM (%)', 'Variação YoY (%)']
    
    return tabela


@st.cache_data
def calcular_share_grupos(df_categoria, nome_categoria):
    # 1. Configuração dos filtros para remover o agregador (Totalizador da Categoria)
    data_rules = {
        'news': ('news.xlsx', 'News/Information'),
        'entretenimento': ('entretenimento.xlsx', 'Entertainment - News'),
        'sports': ('sports.xlsx', 'Sports'),
        'food': ('food.xlsx', 'Lifestyles - Food')
    }
    
    # Configuração dos tamanhos dos grupos conforme sua regra
    group_sizes = {
        'news': (10, 15), 
        'entretenimento': (10, 10),
        'sports': (5, 7), 
        'food': (5, 10)
    }
    
    cat_key = nome_categoria.lower().strip()
    
    # Buscamos o valor que deve ser filtrado (ex: 'News/Information')
    _, filtro_total = data_rules.get(cat_key, (None, None))
    
    # --- TRECHO DE CONTROLE (A CORREÇÃO) ---
    # Criamos o df_limpo removendo a linha que soma a categoria inteira
    # Usamos .str.strip() para garantir que "News/Information " (com espaço) também seja removido
    df_limpo = df_categoria[df_categoria['Media'].astype(str).str.strip() != filtro_total].copy()
    # ---------------------------------------

    if df_limpo.empty:
        return pd.DataFrame()

    top_x, next_y = group_sizes.get(cat_key, (5, 10))

    # 2. Cálculo do Share Mensal Real (sobre a base sem o totalizador)
    df_limpo['Mensal_Total'] = df_limpo.groupby('Date')['Total_Real'].transform('sum')
    df_limpo['share'] = df_limpo['Total_Real'] / df_limpo['Mensal_Total']

    # 3. Rank por média histórica para fixar os players nos grupos
    media_rank = (
        df_limpo.groupby('Media')['share']
        .mean()
        .sort_values(ascending=False)
    )

    group1_players = media_rank.head(top_x).index.tolist()
    group2_players = media_rank.iloc[top_x:top_x + next_y].index.tolist()

    # 4. Agrupar os resultados mensais
    resultados = []
    for data, gp in df_limpo.groupby('Date'):
        s1 = gp[gp['Media'].isin(group1_players)]['share'].sum()
        s2 = gp[gp['Media'].isin(group2_players)]['share'].sum()
        s3 = max(0.0, 1.0 - s1 - s2) # Restante (Cauda Longa)

        resultados.append({
            'Date': data,
            f'Top {top_x} Players': s1,
            f'Próximos {next_y} Players': s2,
            'Players Restantes': s3
        })

    return pd.DataFrame(resultados)


@st.cache_data
def contar_players_ativos(nome_categoria):
    # 1. Regras de arquivos e filtros
    data_rules = {
        'news': ('news.xlsx', 'News/Information'),
        'entretenimento': ('entretenimento.xlsx', 'Entertainment - News'),
        'sports': ('sports.xlsx', 'Sports'),
        'food': ('food.xlsx', 'Lifestyles - Food')
    }
    
    cat_key = nome_categoria.lower().strip()
    arquivo, filtro_total = data_rules.get(cat_key, (None, None))
    
    caminho = f"data/{arquivo}"
    
    if os.path.exists(caminho):
        df_bruto = pd.read_excel(caminho)
        df_bruto.columns = [str(col).strip() for col in df_bruto.columns]

        # Tira o agregador ('News/Information') E tira quem tem 0 de audiência
        col_metrica = 'Total Unique Visitors/Viewers (000)' # ou a sua métrica padrão
        
        df_limpo = df_bruto[
            (df_bruto['Media'].astype(str).str.strip() != filtro_total) & 
            (pd.to_numeric(df_bruto[col_metrica], errors='coerce') > 0)
        ].copy()

        # 3. Criar a coluna de data para o eixo X
        df_limpo['Date'] = pd.to_datetime(
            df_bruto['Year'].astype(str) + '-' + df_bruto['Month'].astype(str).str.zfill(2) + '-01'
        )

        # 4. Contar quantos players únicos existem em cada mês
        contagem = df_limpo.groupby('Date')['Media'].nunique().reset_index()
        contagem.columns = ['Date', 'Quantidade de Players']
        
        return contagem.sort_values('Date')
    
    return pd.DataFrame()


@st.cache_data
def calcular_area_share_top_players(df_categoria, nome_categoria):
    # 1. Configuração de filtros (Data Rules)
    data_rules = {
        'news': ('news.xlsx', 'News/Information'),
        'entretenimento': ('entretenimento.xlsx', 'Entertainment - News'),
        'sports': ('sports.xlsx', 'Sports'),
        'food': ('food.xlsx', 'Lifestyles - Food')
    }
    
    group_sizes = {
        'news': (10, 15), 'entretenimento': (10, 10),
        'sports': (5, 7), 'food': (5, 10)
    }
    
    cat_key = nome_categoria.lower().strip()
    _, filtro_total = data_rules.get(cat_key, (None, None))
    top_x, _ = group_sizes.get(cat_key, (5, 10))
    
    # 2. LIMPEZA INICIAL: Remove apenas o agregador da Comscore
    # df_limpo contém TODOS os veículos (Top + Meio + Pequenos)
    df_limpo = df_categoria[df_categoria['Media'].astype(str).str.strip() != filtro_total].copy()
    
    # 3. CÁLCULO DO SHARE REAL: Baseado na soma de TODOS os veículos ativos
    df_limpo['Mensal_Total'] = df_limpo.groupby('Date')['Total_Real'].transform('sum')
    df_limpo['share'] = df_limpo['Total_Real'] / df_limpo['Mensal_Total']
    
    # 4. IDENTIFICAÇÃO DOS TOP PLAYERS: Rank pela média histórica
    top_players = (
        df_limpo.groupby('Media')['share']
        .mean()
        .nlargest(top_x)
        .index.tolist()
    )
    
    # 5. FILTRAGEM PARA O GRÁFICO: 
    # Mantemos apenas os Top X, mas o valor da coluna 'share' 
    # continua sendo a fatia deles sobre o mercado TOTAL.
    df_top_plot = df_limpo[df_limpo['Media'].isin(top_players)].copy()
    
    return df_top_plot.sort_values(['Date', 'share'], ascending=[True, False])


@st.cache_data
def carregar_dados_dispersao(nome_categoria):
    data_rules = {
        'news': ('news.xlsx', 'News/Information'),
        'entretenimento': ('entretenimento.xlsx', 'Entertainment - News'),
        'sports': ('sports.xlsx', 'Sports'),
        'food': ('food.xlsx', 'Lifestyles - Food')
    }
    
    cat_key = nome_categoria.lower().strip()
    arquivo, filtro_total = data_rules.get(cat_key, (None, None))
    caminho = f"data/{arquivo}"
    
    if os.path.exists(caminho):
        df = pd.read_excel(caminho)
        df.columns = [str(col).strip() for col in df.columns]
        
        # Identificar colunas
        col_users = next((c for c in df.columns if 'Unique Visitors' in c), None)
        col_visits = next((c for c in df.columns if 'Total Visits' in c), None)
            
        # Limpeza e Conversão
        df = df[df['Media'].astype(str).str.strip() != filtro_total].copy()
        df[col_users] = pd.to_numeric(df[col_users], errors='coerce')
        df[col_visits] = pd.to_numeric(df[col_visits], errors='coerce')
        
        # Criar coluna Date para o seletor
        df['Date'] = pd.to_datetime(
            df['Year'].astype(str) + '-' + df['Month'].astype(str).str.zfill(2) + '-01'
        )
        
        # Aplicar Escalas
        df['Usuarios_Scatter'] = df[col_users] * 1_000_000
        df['Visitas_Scatter'] = df[col_visits] * 1_000
        
        return df.dropna(subset=['Usuarios_Scatter', 'Visitas_Scatter'])
    return pd.DataFrame()