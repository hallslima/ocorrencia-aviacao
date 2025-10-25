import streamlit as st
import pandas as pd
import altair as alt
import json
import re # Importar a biblioteca de expressões regulares
import plotly.express as px
# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard | Segurança de Voo CENIPA",
    layout="wide"
)

# --- 2. CARREGAR E PREPARAR OS DADOS (EM CACHE) ---
@st.cache_data
def load_data():
    """Carrega, limpa e pré-processa os arquivos CSV do CENIPA."""
    try:
        na_values = ['***', 'NULL', 'NA', 'N/A', '', '****']
        encoding_type = 'windows-1252'

        # Carregar arquivos CSV
        df_ocorrencia = pd.read_csv('data/ocorrencia.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_aeronave = pd.read_csv('data/aeronave.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_fator = pd.read_csv('data/fator_contribuinte.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_tipo = pd.read_csv('data/ocorrencia_tipo.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_recomendacao = pd.read_csv('data/recomendacao.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)

        # --- Limpeza Padrão ---
        df_ocorrencia['ocorrencia_dia'] = pd.to_datetime(df_ocorrencia['ocorrencia_dia'], dayfirst=True, errors='coerce')
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_dia'].dt.year

        # Limpeza simplificada das coordenadas
        def clean_coord(coord_str):
            if pd.isna(coord_str): return None
            try:
                cleaned_stage1 = str(coord_str).replace(',', '.').strip()
                match = re.search(r"(-?\d+(\.\d+)?)", cleaned_stage1)
                if match:
                    val = float(match.group(1))
                    if -180 <= val <= 180: return val
                return None
            except: return None

        df_ocorrencia['latitude'] = df_ocorrencia['ocorrencia_latitude'].apply(clean_coord)
        df_ocorrencia['longitude'] = df_ocorrencia['ocorrencia_longitude'].apply(clean_coord)

        # Filtrar faixa Brasil e remover NAs essenciais
        df_ocorrencia = df_ocorrencia[
            (df_ocorrencia['latitude'].between(-34, 6, inclusive='both')) &
            (df_ocorrencia['longitude'].between(-74, -34, inclusive='both'))
        ]
        df_ocorrencia = df_ocorrencia.dropna(subset=['ocorrencia_ano', 'ocorrencia_uf', 'latitude', 'longitude'])
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_ano'].astype(int)

        df_aeronave['aeronave_fatalidades_total'] = pd.to_numeric(df_aeronave['aeronave_fatalidades_total'], errors='coerce').fillna(0)
        df_aeronave['aeronave_registro_segmento'] = df_aeronave['aeronave_registro_segmento'].fillna('INDETERMINADO')
        df_aeronave['aeronave_fase_operacao'] = df_aeronave['aeronave_fase_operacao'].fillna('INDETERMININA')

        df_fator = df_fator.dropna(subset=['fator_area'])
        df_tipo = df_tipo.dropna(subset=['ocorrencia_tipo'])
        df_recomendacao['recomendacao_status'] = df_recomendacao['recomendacao_status'].fillna('INDETERMINADO')

        # Carregar o arquivo GeoJSON para o mapa base
        try:
            with open('data/br_states.json', 'r') as f:
                geojson_br = json.load(f)
        except FileNotFoundError:
            st.error("Arquivo 'data/br_states.json' não encontrado. Necessário para o mapa base.")
            return None

        # Retornar dicionário
        return {
            "ocorrencia": df_ocorrencia,
            "aeronave": df_aeronave,
            "fator": df_fator,
            "tipo": df_tipo,
            "recomendacao": df_recomendacao,
            "geojson_br": geojson_br
        }

    # Tratamento de erros
    except FileNotFoundError as e:
        st.error(f"Erro: Arquivo CSV não encontrado. Verifique 'data/'. Detalhe: {e}")
        return None
    except UnicodeDecodeError:
        st.error("Erro de codificação (Encoding). Tente 'latin-1' ou 'utf-8'.")
        return None
    except Exception as e:
        st.error(f"Erro inesperado no load_data: {e}")
        return None


# Carregar os dados
data_dict = load_data()
if data_dict is None: st.stop()

# Desempacotar
df_ocorrencia = data_dict['ocorrencia']
df_aeronave = data_dict['aeronave']
df_fator = data_dict['fator']
df_tipo = data_dict['tipo']
df_recomendacao = data_dict['recomendacao']
geojson_br = data_dict['geojson_br']

# --- 3. SEÇÃO 1: TÍTULO E PANORAMA GERAL ---
st.title("Decolando com Segurança: Onde Reside o Risco Aéreo no Brasil?")
st.warning(
    "**Problemática:** Onde realmente reside o real risco na aviação brasileira?"
)

st.header("Seção 1: O Panorama Geral das Ocorrências (2007-2025)")
st.markdown("Primeiro, vamos entender o contexto. Quantas ocorrências temos e qual a gravidade delas?")

# Calcular o novo KPI
total_acidentes = df_ocorrencia[df_ocorrencia['ocorrencia_classificacao'] == 'ACIDENTE'].shape[0]

# KPIs da Seção 1 (Linha 1)
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric(
    "Total de Ocorrências (Geral)",
    f"{df_ocorrencia.shape[0]:,}",
    help="Soma de todos os eventos: Acidentes, Incidentes Graves e Incidentes."
)
kpi2.metric(
    "Total de ACIDENTES",
    f"{total_acidentes:,}",
    help="Ocorrências com dano substancial à aeronave ou lesões graves/fatais."
)
kpi3.metric(
    "Total de Fatalidades",
    f"{int(df_aeronave['aeronave_fatalidades_total'].sum()):,}",
    help="Número total de fatalidades registradas em todos os acidentes."
)

# --- DEFINIÇÃO DO MAPA DE CORES (USADO NOS DOIS GRÁFICOS) ---
domain_classificacao = ['ACIDENTE', 'INCIDENTE GRAVE', 'INCIDENTE']
range_cores = ['#d62728', "#ffd30e", "#0c72e7"] # Vermelho, Laranja, Amarelo

# Gráfico de Classificação e Definições (Linha 2)
col_grafico, col_definicoes = st.columns(2)

with col_grafico:
    # Gráfico de BARRAS para Classificação
    classificacao_data = df_ocorrencia['ocorrencia_classificacao'].value_counts().reset_index()
    chart_classif = alt.Chart(classificacao_data).mark_bar().encode(
        x=alt.X('ocorrencia_classificacao', title='Classificação', sort='-y'),
        y=alt.Y('count', title='Nº de Ocorrências'),
        # --- APLICAÇÃO DO MAPA DE CORES (GRÁFICO 1) ---
        color=alt.Color('ocorrencia_classificacao',
                        title="Classificação",
                        legend=None, # Legenda é redundante aqui
                        scale=alt.Scale(domain=domain_classificacao, range=range_cores)),
        tooltip=['ocorrencia_classificacao', 'count']
    ).properties(
        title="Ocorrências por Classificação"
    )
    st.altair_chart(chart_classif, use_container_width=True)

with col_definicoes:
    st.markdown("<br/>", unsafe_allow_html=True)
    with st.expander("Definições oficiais", expanded=True):
        st.markdown("""* **ACIDENTE:** Ocorrência com **lesão grave/fatal** ou **dano substancial** à aeronave. 
                    \n\n* **INCIDENTE GRAVE:** Ocorrência onde **um acidente quase ocorreu**. 
                    \n\n* **INCIDENTE:** Outra ocorrência que **afete ou possa afetar a segurança**.""", help="Baseado nas normas CENIPA/ICAO.")

# Gráfico 2: Série Temporal
st.subheader("Estamos Melhorando ou Piorando?")
st.markdown("A contagem de ocorrências (`ACIDENTE`, `INCIDENTE GRAVE`, `INCIDENTE`) ao longo do tempo.")

# Agrupar por ano e classificação
ocorrencias_ano = df_ocorrencia[df_ocorrencia['ocorrencia_ano'] >= 2007].groupby(
    ['ocorrencia_ano', 'ocorrencia_classificacao']
).size().reset_index(name='contagem')

# Criar o gráfico de linha
chart_temporal = alt.Chart(ocorrencias_ano).mark_line(point=True).encode(
    x=alt.X('ocorrencia_ano:O', title='Ano da Ocorrência'),
    y=alt.Y('contagem:Q', title='Número de Ocorrências'),
    # --- APLICAÇÃO DO MAPA DE CORES (GRÁFICO 2) ---
    color=alt.Color('ocorrencia_classificacao',
                    title='Classificação',
                    scale=alt.Scale(domain=domain_classificacao, range=range_cores)),
    tooltip=['ocorrencia_ano', 'ocorrencia_classificacao', 'contagem']
).properties(
    title='Ocorrências Aeronáuticas por Ano'
).interactive()
st.altair_chart(chart_temporal, use_container_width=True)
st.markdown("---")

# --- 4. SEÇÃO 2: ONDE ESTÁ O RISCO? (SEGMENTO, FASE E TIPO) ---
st.header("Seção 2: Onde o Risco se Concentra?")
st.markdown("""
O público geral teme a aviação comercial (voos de linha aérea), mas será que é ela a principal fonte de risco? 
Aqui, **focamos apenas em ACIDENTES** para entender onde o perigo é maior.
""")

col1, col2, col3 = st.columns(3)

# --- Merge de ACIDENTES (usado em 2 gráficos) ---
# 1. Juntar aeronave com ocorrencia para filtrar só acidentes
df_aeronave_acidentes = pd.merge(
    df_aeronave,
    df_ocorrencia[['codigo_ocorrencia', 'ocorrencia_classificacao']],
    left_on='codigo_ocorrencia2',
    right_on='codigo_ocorrencia',
    how='left' # Usar left join para manter todas as aeronaves
)
# 2. Filtrar apenas por ACIDENTE
df_aeronave_acidentes = df_aeronave_acidentes[
    df_aeronave_acidentes['ocorrencia_classificacao'] == 'ACIDENTE'
]

with col1:

    st.subheader("Risco por Segmento")

   

    # 3. Contar por segmento

    segmento_data = df_aeronave_acidentes['aeronave_registro_segmento'].value_counts().nlargest(10).reset_index()

   

    chart_segmento = alt.Chart(segmento_data).mark_bar().encode(

        x=alt.X('count', title='Nº de Acidentes'),

        y=alt.Y('aeronave_registro_segmento', title='Segmento da Aviação', sort='-x'),

        tooltip=['aeronave_registro_segmento', 'count']

    ).properties(

        title='Top 10 Segmentos por Nº de ACIDENTES'

    ).interactive()

    st.altair_chart(chart_segmento, use_container_width=True)

    st.info("💡 **Insight:** Aviação **PARTICULAR** lidera com mais que o drobro de incidentes do 2º colocado (possíveis fatores: número de vôos e regulação mais branda que a comercial).")

with col2:
    st.subheader("Risco por Fase do Voo")
    
    # Contar por fase de operação (usando o df_aeronave_acidentes que já filtramos)
    fase_data = df_aeronave_acidentes['aeronave_fase_operacao'].value_counts().nlargest(10).reset_index()
    
    # --- GRÁFICO DE PIRULITO (Lollipop Chart) ---
    # Gráfico base
    base_fase = alt.Chart(fase_data).encode(
        y=alt.Y('aeronave_fase_operacao', title='Fase da Operação', sort='-x'),
        x=alt.X('count', title='Nº de Acidentes'),
        tooltip=['aeronave_fase_operacao', 'count']
    )
    # Linha
    line_fase = base_fase.mark_rule(color='lightgray').encode(size=alt.value(2))
    # Ponto
    point_fase = base_fase.mark_point(filled=True, size=100, color='red')
    # Combina os gráficos
    chart_fase = (line_fase + point_fase).properties(
        title='Top 10 Fases de Voo por Nº de ACIDENTES'
    ).interactive()
    
    st.altair_chart(chart_fase, use_container_width=True)
    st.info("💡 **Insight:** **DECOLAGEM**, **POUSO** e **CRUZEIRO** são as mais críticas.")

with col3:
    st.subheader("Tipos de Ocorrências em Acidentes")

    # --- CÓDIGO CORRIGIDO ---
    # Agora usamos o nome correto da coluna de df_tipo, que é 'codigo_ocorrencia1'.
    df_tipo_com_classificacao = pd.merge(
        df_tipo,
        df_ocorrencia[['codigo_ocorrencia', 'ocorrencia_classificacao']],
        left_on='codigo_ocorrencia1',  # A CHAVE CORRETA!
        right_on='codigo_ocorrencia',
        how='left'
    )

    # 2. Filtrar o dataframe resultante para manter apenas os ACIDENTES.
    df_tipo_acidentes = df_tipo_com_classificacao[
        df_tipo_com_classificacao['ocorrencia_classificacao'] == 'ACIDENTE'
    ]

    # 3. Contar os tipos de ocorrência a partir do dataframe JÁ FILTRADO.
    tipo_data = df_tipo_acidentes['ocorrencia_tipo'].value_counts().nlargest(10).reset_index()

    # Renomear colunas para o Plotly
    tipo_data.columns = ['tipo', 'contagem']

    # --- GRÁFICO DE TREEMAP com PLOTLY ---
    fig_treemap = px.treemap(
        tipo_data,
        path=['tipo'],
        values='contagem',
        title='Top 10 Tipos de ACIDENTES',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )

    # Melhora a aparência dos rótulos
    fig_treemap.update_traces(
        textinfo='label+percent root',
        insidetextfont=dict(size=14)
    )

    # Ajusta as margens para o título não ficar cortado
    fig_treemap.update_layout(margin = dict(t=50, l=25, r=25, b=25))

    # Usa st.plotly_chart para exibir o gráfico
    st.plotly_chart(fig_treemap, use_container_width=True)

    st.info("💡 **Insight:** **PERDA DE CONTROLE**, **FALHA DO MOTOR** são frequentes.")

st.markdown("---")

# --- 5. SEÇÃO 3: ONDE O RISCO OCORRE? (GEOGRAFIA - MAPA DE PONTOS E BARRAS) ---
# --- INÍCIO DA ATUALIZAÇÃO (CORRIGINDO PROJEÇÃO) ---
st.header("Seção 3: Onde o Risco Ocorre? (Análise Geográfica)")
st.markdown("Visualizamos a **dispersão** (mapa de pontos) e o **volume** (gráfico de barras) dos **ACIDENTES** por estado (UF).")

col_mapa, col_barras_uf = st.columns(2)

with col_mapa:
    st.subheader("Mapa de Dispersão dos Acidentes")
    # Preparar os dados para os pontos
    if all(col in df_ocorrencia.columns for col in ['latitude', 'longitude', 'ocorrencia_cidade', 'ocorrencia_uf', 'ocorrencia_dia', 'ocorrencia_classificacao']):
        df_acidentes_mapa = df_ocorrencia[
            df_ocorrencia['ocorrencia_classificacao'] == 'ACIDENTE'
        ][['latitude', 'longitude', 'ocorrencia_cidade', 'ocorrencia_uf', 'ocorrencia_dia']].copy()
        df_acidentes_mapa = df_acidentes_mapa.dropna(subset=['latitude', 'longitude'])

        if df_acidentes_mapa.empty:
            st.warning("Não há dados de acidentes com coordenadas válidas para exibir no mapa.")
        else:
            try:
                # Carregar o GeoJSON para o mapa base
                states_geojson_data = alt.Data(values=geojson_br, format=alt.DataFormat(type='json', property='features'))

                # Criar o Mapa Base com projeção
                base_map = alt.Chart(states_geojson_data).mark_geoshape(
                    fill='#AAAAAA',
                    stroke='white',
                    strokeWidth=0.5
                ).project( # Aplicar projeção diretamente aqui
                     type='mercator',
                     scale=550,
                     center=[-54, -15]
                )

                # Criar a Camada de Pontos COM A MESMA projeção
                points_layer = alt.Chart(df_acidentes_mapa).mark_circle(
                    size=15,
                    opacity=0.6
                ).encode(
                    longitude='longitude:Q',
                    latitude='latitude:Q',
                    color=alt.value('red'),
                    tooltip=[
                        alt.Tooltip('ocorrencia_cidade', title='Cidade'),
                        alt.Tooltip('ocorrencia_uf', title='UF'),
                        alt.Tooltip('ocorrencia_dia', title='Data', format='%d/%m/%Y')
                    ]
                ).project( # Aplicar a MESMA projeção diretamente aqui
                    type='mercator',
                    scale=550,
                    center=[-54, -15]
                )

                # Combinar as camadas e exibir
                final_map_points = (base_map + points_layer).properties(
                    title='Localização Geográfica dos ACIDENTES',
                    width=500 # Manter largura explícita
                ).interactive()

                st.altair_chart(final_map_points, use_container_width=False) # Manter False

            except Exception as e:
                st.error(f"Erro ao gerar o mapa de pontos: {e}")
                st.write("Verificando os primeiros dados de coordenadas:")
                st.dataframe(df_acidentes_mapa[['latitude', 'longitude']].head())


    else:
        st.error("Colunas necessárias para o mapa não encontradas no DataFrame 'df_ocorrencia'.")


with col_barras_uf:
    st.subheader("Volume de Acidentes por Estado")
    # Preparar dados
    df_acidentes_geo_bar = df_ocorrencia[df_ocorrencia['ocorrencia_classificacao'] == 'ACIDENTE']
    if not df_acidentes_geo_bar.empty:
        uf_data_bar = df_acidentes_geo_bar['ocorrencia_uf'].value_counts().nlargest(15).reset_index()
        uf_data_bar.columns = ['ocorrencia_uf', 'contagem_acidentes']

        # Criar o Gráfico de Barras por UF
        chart_uf_bar = alt.Chart(uf_data_bar).mark_bar().encode(
            y=alt.Y('ocorrencia_uf', title='Estado (UF)', sort='-x'),
            x=alt.X('contagem_acidentes', title='Nº de Acidentes'),
            tooltip=['ocorrencia_uf', 'contagem_acidentes']
        ).properties(
            title='Top 15 Estados por Nº de ACIDENTES'
        ).interactive()
        st.altair_chart(chart_uf_bar, use_container_width=True)
    else:
        st.warning("Não há dados de acidentes para gerar o gráfico de barras por UF.")

st.info(
    "💡 **Insight Combinado:** O mapa mostra a **dispersão** dos acidentes, concentrados no Centro-Oeste, Sudeste e Sul. "
    "O gráfico de barras confirma o **volume**, destacando SP, MT, RS, PR e MG."
)
# --- FIM DA ATUALIZAÇÃO ---

st.markdown("---")


# --- 6. SEÇÃO 4: A CAUSA RAIZ (MÁQUINA VS. HOMEM) ---
st.header("Seção 4: A Causa Raiz - Máquina ou Homem?")
st.markdown("Análise dos **Fatores Contribuintes** para entender a origem das ocorrências.")
df_fator_ocorrencia = pd.merge(df_fator, df_ocorrencia[['codigo_ocorrencia', 'ocorrencia_classificacao']], left_on='codigo_ocorrencia3', right_on='codigo_ocorrencia', how='inner')

col_fator1, col_fator2 = st.columns(2)
with col_fator1:
    st.subheader("Visão Geral dos Fatores")
    fator_area_data = df_fator_ocorrencia['fator_area'].value_counts().reset_index()
    chart_area = alt.Chart(fator_area_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Menções'), y=alt.Y('fator_area', title='Área do Fator', sort='-x'), tooltip=['fator_area', 'count']
    ).properties(title='Causas Raízes (Geral)').interactive()
    st.altair_chart(chart_area, use_container_width=True)
with col_fator2:
    st.subheader("Zoom no 'Fator Operacional'")
    df_fator_operacional = df_fator_ocorrencia[df_fator_ocorrencia['fator_area'] == 'FATOR OPERACIONAL']
    fator_nome_data = df_fator_operacional['fator_nome'].value_counts().nlargest(10).reset_index()
    chart_fator_nome = alt.Chart(fator_nome_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Menções'), y=alt.Y('fator_nome', title='Fator Específico', sort='-x'), tooltip=['fator_nome', 'count']
    ).properties(title='Top 10 Fatores Humanos').interactive()
    st.altair_chart(chart_fator_nome, use_container_width=True)
st.success("🎯 **A Resposta:** O **FATOR OPERACIONAL** é o mais contribuinte, superando Fator Humano e Falha Material. **JULGAMENTO DE PILOTAGEM** e **APLICAÇÃO DE COMANDOS** são os principais desafios.")
st.markdown("---")

# --- 7. SEÇÃO 5: NOSSAS AÇÕES ESTÃO FUNCIONANDO? (STATUS DAS RECOMENDAÇÕES) ---
st.header("Seção 5: Nossas Ações Estão Funcionando? (Status das Recomendações)")
st.markdown("""
Investigar é o primeiro passo, mas agir é o que previne futuros acidentes. Analisamos o status de todas as recomendações de segurança emitidas pelo CENIPA para avaliar sua eficácia.
""")

st.subheader("Proporção do Status de Adoção das Recomendações (Treemap)")

# --- PREPARAÇÃO DOS DADOS ---
recomendacao_data = df_recomendacao['recomendacao_status'].value_counts().reset_index()
recomendacao_data.columns = ['status', 'contagem'] # Renomear colunas para clareza no Plotly

# --- GRÁFICO DE TREEMAP COM PLOTLY EXPRESS ---
fig_treemap_recomendacao = px.treemap(
    recomendacao_data,
    path=['status'], # Cria uma hierarquia simples
    values='contagem',
    title='Status de Adoção das Recomendações (CENIPA)',
    color='status', # Colore os retângulos com base no status
    color_discrete_map={
        # Mapeamento de cores semânticas para corresponder ao que você já tinha
        'ADOTADA': '#2ca02c',                 # Verde
        'NÃO ADOTADA': '#d62728',             # Vermelho
        'INDETERMINADO': '#7f7f7f',           # Cinza
        'ADOTADA DE FORMA ALTERNATIVA': '#1f77b4', # Azul
        'AGUARDANDO RESPOSTA': "#b9b732"      # Amarelo/Mostarda
    },
    hover_data={'contagem': True, 'status': True} # Informações extras ao passar o mouse
)

# Melhorar a aparência dos rótulos e layout
fig_treemap_recomendacao.update_traces(
    textinfo='label+percent entry', # Mostra rótulo e porcentagem
    insidetextfont=dict(size=14, color='white') # Cor e tamanho da fonte interna
)

fig_treemap_recomendacao.update_layout(
    margin=dict(t=50, l=25, r=25, b=25), # Ajusta as margens
    # centraliza o título
    title_x=0.5
)

st.plotly_chart(fig_treemap_recomendacao, use_container_width=True)

st.info("💡 **Insight:** A maioria das recomendações foi **'ADOTADA'**, porém o volume de **'INDETERMINADO'** indica gargalo no feedback. O Treemap destaca visualmente a proporção de cada status.")
st.markdown("---")

# --- 8. SEÇÃO 6: SOLUÇÕES E RECOMENDAÇÕES ---
st.header("Seção 6: Soluções e Recomendações Estratégicas (Para a ANAC)")
st.markdown("Com base na análise, propomos as seguintes ações:")
rec1, rec2, rec3 = st.columns(3)
with rec1:
    st.subheader("1. 🎯 Foco na Fiscalização")
    st.markdown("Priorizar **Aviação Geral (Particular e Agrícola)** e os **estados do Centro-Oeste e Sudeste** (Seções 2 e 3).")
with rec2:
    st.subheader("2. 🧠 Foco no Treinamento")
    st.markdown("Reforçar **CRM** e **ADM**, especialmente para **Pouso** e **Decolagem** (Seções 2 e 4).")
with rec3:
    st.subheader("3. ✈️ Foco no *Feedback*")
    st.markdown("Reforçar manutenção na aviação geral ('Falha de Motor', Seção 2) e cobrar **'AGUARDANDO RESPOSTA'** (Seção 5).")