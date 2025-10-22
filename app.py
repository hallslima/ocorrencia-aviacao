import streamlit as st
import pandas as pd
import altair as alt
# import json # Removido - Não precisamos mais para o mapa

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard | Segurança de Voo CENIPA",
    layout="wide"
)

# --- 2. CARREGAR E PREPARAR OS DADOS (EM CACHE) ---
# Esta função é executada apenas uma vez para carregar e limpar todos os dados.
@st.cache_data
def load_data():
    """Carrega, limpa e pré-processa os arquivos CSV do CENIPA."""
    try:
        # Definir valores que serão tratados como Nulos
        na_values = ['***', 'NULL', 'NA', 'N/A', '']
        encoding_type = 'windows-1252' 
        
        # Carregar os arquivos CSV necessários
        df_ocorrencia = pd.read_csv('data/ocorrencia.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_aeronave = pd.read_csv('data/aeronave.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_fator = pd.read_csv('data/fator_contribuinte.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_tipo = pd.read_csv('data/ocorrencia_tipo.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type)
        df_recomendacao = pd.read_csv('data/recomendacao.csv', sep=';', na_values=na_values, low_memory=False, encoding=encoding_type) 
        
        # --- Limpeza e Processamento ---
        
        # 1. Tabela OCORRÊNCIA
        df_ocorrencia['ocorrencia_dia'] = pd.to_datetime(df_ocorrencia['ocorrencia_dia'], dayfirst=True, errors='coerce')
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_dia'].dt.year
        df_ocorrencia = df_ocorrencia.dropna(subset=['ocorrencia_ano', 'ocorrencia_uf'])
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_ano'].astype(int)
        
        # 2. Tabela AERONAVE
        df_aeronave['aeronave_fatalidades_total'] = pd.to_numeric(df_aeronave['aeronave_fatalidades_total'], errors='coerce').fillna(0)
        df_aeronave['aeronave_registro_segmento'] = df_aeronave['aeronave_registro_segmento'].fillna('INDETERMINADO')
        df_aeronave['aeronave_fase_operacao'] = df_aeronave['aeronave_fase_operacao'].fillna('INDETERMININA')

        # 3. Tabela FATOR
        df_fator = df_fator.dropna(subset=['fator_area'])
        
        # 4. Tabela TIPO
        df_tipo = df_tipo.dropna(subset=['ocorrencia_tipo'])
        
        # 5. Tabela RECOMENDAÇÃO
        df_recomendacao['recomendacao_status'] = df_recomendacao['recomendacao_status'].fillna('INDETERMINADO')
        
        # REMOVIDO: Carregamento e enriquecimento do GeoJSON

        # Retornar um dicionário com os DataFrames limpos
        return {
            "ocorrencia": df_ocorrencia,
            "aeronave": df_aeronave,
            "fator": df_fator,
            "tipo": df_tipo,
            "recomendacao": df_recomendacao
            # "geojson_br_enriquecido": geojson_br # Removido
        }

    except FileNotFoundError as e:
        st.error(f"Erro ao carregar os dados. Verifique se o arquivo CSV está no local correto (pasta 'data/'). Detalhe: {e}")
        return None
    except UnicodeDecodeError:
        st.error(f"Erro de codificação (Encoding). Tente alterar o 'encoding_type' na função load_data() para 'latin-1' ou 'utf-8'.")
        return None
    except Exception as e: # Captura outros erros
        st.error(f"Ocorreu um erro inesperado durante o carregamento/processamento: {e}")
        return None


# Carregar os dados
data_dict = load_data()

# Se os dados não forem carregados, interrompe o app
if data_dict is None:
    st.stop()

# Desempacotar os dados para facilitar o uso
df_ocorrencia = data_dict['ocorrencia']
df_aeronave = data_dict['aeronave']
df_fator = data_dict['fator']
df_tipo = data_dict['tipo']
df_recomendacao = data_dict['recomendacao']
# geojson_br_enriquecido = data_dict['geojson_br_enriquecido'] # Removido

# --- 3. SEÇÃO 1: TÍTULO E PANORAMA GERAL ---
st.title("Decolando com Segurança: Onde Reside o Risco Aéreo no Brasil?")
st.warning(
    "**Problemática:** Onde realmente reside o maior risco na aviação civil brasileira? "
    "Nossa análise investiga se o perigo está nas **Máquinas** (falhas mecânicas) ou no **Fator Humano** (decisões e operações)."
)

st.header("Seção 1: O Panorama Geral das Ocorrências")
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

# Gráfico de Classificação e Definições (Linha 2)
col_grafico, col_definicoes = st.columns(2)

with col_grafico:
    # Gráfico de BARRAS para Classificação
    classificacao_data = df_ocorrencia['ocorrencia_classificacao'].value_counts().reset_index()
    chart_classif = alt.Chart(classificacao_data).mark_bar().encode(
        x=alt.X('ocorrencia_classificacao', title='Classificação', sort='-y'), 
        y=alt.Y('count', title='Nº de Ocorrências'),
        color=alt.Color('ocorrencia_classificacao', title="Classificação"),
        tooltip=['ocorrencia_classificacao', 'count']
    ).properties(
        title="Ocorrências por Classificação"
    )
    st.altair_chart(chart_classif, use_container_width=True)

with col_definicoes:
    # Adicionar um espaço para alinhar verticalmente com o título do gráfico
    st.markdown("<br/>", unsafe_allow_html=True) 
    
    # Definições
    with st.expander("Definições oficiais de 'Acidente', 'Incidente Grave' e 'Incidente'", expanded=True):
        st.markdown(
            """
            De acordo com as normas do CENIPA (baseadas na legislação brasileira e no Anexo 13 da ICAO), as classificações significam:

            * **ACIDENTE:**
                * Ocorrência onde (a) **uma pessoa sofre lesão grave ou falece**, ou (b) **a aeronave sofre dano ou falha estrutural** que exija grande reparo.

            * **INCIDENTE GRAVE:**
                * Ocorrência em que **um acidente quase ocorreu**. A diferença está apenas nas **consequências** (que foram evitadas).
                * *Ex: Quase colisão, pouso em pista fechada.*

            * **INCIDENTE:**
                * Ocorrência, que não seja um acidente, que **afete ou possa afetar a segurança** da operação.
                * *Ex: Colisão com ave sem dano substancial.*
            """,
            help="Definições baseadas nas normas NSCA 3-6 e 3-13 do Comando da Aeronáutica e Anexo 13 da ICAO."
        )

# Gráfico 1: Série Temporal
st.subheader("Estamos Melhorando ou Piorando?")
st.markdown("A contagem de ocorrências (`ACIDENTE`, `INCIDENTE GRAVE`, `INCIDENTE`) ao longo do tempo.")

# Agrupar por ano e classificação
ocorrencias_ano = df_ocorrencia[df_ocorrencia['ocorrencia_ano'] >= 2007].groupby(
    ['ocorrencia_ano', 'ocorrencia_classificacao']
).size().reset_index(name='contagem')

# Criar o gráfico de linha
chart_temporal = alt.Chart(ocorrencias_ano).mark_line(point=True).encode(
    x=alt.X('ocorrencia_ano:O', title='Ano da Ocorrência'), # 'O' para Ordinal (ano)
    y=alt.Y('contagem:Q', title='Número de Ocorrências'),
    color=alt.Color('ocorrencia_classificacao', title='Classificação'),
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
    st.info("💡 **Insight:** A aviação **PARTICULAR** e **AGRÍCOLA** somam a vasta maioria dos acidentes.")

with col2:
    st.subheader("Risco por Fase do Voo")
    
    # Contar por fase de operação (usando o df_aeronave_acidentes que já filtramos)
    fase_data = df_aeronave_acidentes['aeronave_fase_operacao'].value_counts().nlargest(10).reset_index()
    
    chart_fase = alt.Chart(fase_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Acidentes'),
        y=alt.Y('aeronave_fase_operacao', title='Fase da Operação', sort='-x'),
        tooltip=['aeronave_fase_operacao', 'count']
    ).properties(
        title='Top 10 Fases de Voo por Nº de ACIDENTES'
    ).interactive()
    st.altair_chart(chart_fase, use_container_width=True)
    st.info("💡 **Insight:** **POUSO**, **DECOLAGEM** e **VOO A BAIXA ALTURA** são as fases mais críticas.")

with col3:
    st.subheader("Tipos de Ocorrências")
    
    # Usar a tabela df_tipo (não precisa filtrar por acidente, é o tipo do evento em si)
    tipo_data = df_tipo['ocorrencia_tipo'].value_counts().nlargest(10).reset_index()
    
    chart_tipo = alt.Chart(tipo_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Ocorrências'),
        y=alt.Y('ocorrencia_tipo', title='Tipo de Ocorrência', sort='-x'),
        tooltip=['ocorrencia_tipo', 'count']
    ).properties(
        title='Top 10 Tipos de Ocorrências (Geral)'
    ).interactive()
    st.altair_chart(chart_tipo, use_container_width=True)
    st.info("💡 **Insight:** 'FALHA DO MOTOR EM VOO' e 'PERDA DE CONTROLE EM VOO' são os eventos mais comuns.")

st.markdown("---")


# --- 5. SEÇÃO 3: ONDE O RISCO OCORRE? (GEOGRAFIA - COM GRÁFICO DE BARRAS) ---
st.header("Seção 3: Onde o Risco Ocorre? (Análise Geográfica)")
st.markdown("""
Identificamos os segmentos e fases, mas *onde* no Brasil esses acidentes mais acontecem? 
Focamos nos estados (UF) com maior número de **ACIDENTES**.
""")

# --- INÍCIO DA ATUALIZAÇÃO (VOLTANDO AO GRÁFICO DE BARRAS) ---

# 1. Preparar nossos dados: Filtrar ACIDENTES e contar por UF
df_acidentes_geo = df_ocorrencia[df_ocorrencia['ocorrencia_classificacao'] == 'ACIDENTE']
uf_data = df_acidentes_geo['ocorrencia_uf'].value_counts().nlargest(15).reset_index()
uf_data.columns = ['ocorrencia_uf', 'contagem_acidentes'] # Renomear colunas para clareza

# 2. Criar o Gráfico de Barras por UF
chart_uf = alt.Chart(uf_data).mark_bar().encode(
    x=alt.X('contagem_acidentes', title='Nº de Acidentes'),
    y=alt.Y('ocorrencia_uf', title='Estado (UF)', sort='-x'), # Ordena do maior para o menor
    tooltip=['ocorrencia_uf', 'contagem_acidentes']
).properties(
    title='Top 15 Estados por Nº de ACIDENTES'
).interactive()

st.altair_chart(chart_uf, use_container_width=True)
st.info(
    "💡 **Insight:** O risco não está concentrado apenas em estados com grande volume de voos (como SP), "
    "mas também em estados com forte **Aviação Agrícola e Particular** (MT, GO, MS, RS), "
    "reforçando os insights da Seção 2."
)
st.markdown("*(Nota: Tentamos implementar um mapa de calor, mas enfrentamos problemas de renderização. O gráfico de barras acima transmite a informação essencial.)*")

# --- FIM DA ATUALIZAÇÃO ---

st.markdown("---")


# --- 6. SEÇÃO 4: A CAUSA RAIZ (MÁQUINA VS. HOMEM) ---
st.header("Seção 4: A Causa Raiz - Máquina ou Homem?")
st.markdown("""
Esta é a revelação central da nossa história. Analisamos a tabela de **Fatores Contribuintes** para responder à nossa problemática inicial.
""")

col_fator1, col_fator2 = st.columns(2)

with col_fator1:
    st.subheader("Visão Geral dos Fatores Contribuintes")
    
    # Contar por 'fator_area'
    fator_area_data = df_fator['fator_area'].value_counts().reset_index()
    
    chart_area = alt.Chart(fator_area_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Menções'),
        y=alt.Y('fator_area', title='Área do Fator', sort='-x'),
        tooltip=['fator_area', 'count']
    ).properties(
        title='Causas Raízes das Ocorrências'
    ).interactive()
    st.altair_chart(chart_area, use_container_width=True)

with col_fator2:
    st.subheader("Zoom no 'Fator Humano'")
    
    # 1. Filtrar o DataFrame apenas por FATOR HUMANO
    df_fator_humano = df_fator[df_fator['fator_area'] == 'FATOR HUMANO']
    
    # 2. Contar os fatores específicos
    fator_nome_data = df_fator_humano['fator_nome'].value_counts().nlargest(10).reset_index()
    
    chart_fator_nome = alt.Chart(fator_nome_data).mark_bar().encode(
        x=alt.X('count', title='Nº de Menções'),
        y=alt.Y('fator_nome', title='Fator Específico', sort='-x'),
        tooltip=['fator_nome', 'count']
    ).properties(
        title='Top 10 Fatores Humanos Contribuintes'
    ).interactive()
    st.altair_chart(chart_fator_nome, use_container_width=True)

st.success(
    "🎯 **A Resposta (O Clímax):** A análise é inequívoca. O **FATOR HUMANO** é, de longe, "
    "a área mais contribuinte para ocorrências, superando 'Fator Material' (falha da máquina) "
    "e 'Fator Operacional' (ambiente/infraestrutura). "
    "Especificamente, **'JULGAMENTO DE PILOTAGEM'** e **'PROCESSO DECISÓRIO'** são os principais desafios, "
    "indicando que as falhas são mais de decisão do que de habilidade técnica."
)
st.markdown("---")

# --- 7. SEÇÃO 5: NOSSAS AÇÕES ESTÃO FUNCIONANDO? (RECOMENDAÇÕES) ---
st.header("Seção 5: Nossas Ações Estão Funcionando? (Status das Recomendações)")
st.markdown("""
Investigar é o primeiro passo, mas agir é o que previne futuros acidentes. 
Analisamos o status de todas as recomendações de segurança emitidas pelo CENIPA.
""")

# Contar por status
recomendacao_data = df_recomendacao['recomendacao_status'].value_counts().nlargest(10).reset_index()

chart_recomendacao = alt.Chart(recomendacao_data).mark_bar().encode(
    x=alt.X('count', title='Nº de Recomendações'),
    y=alt.Y('recomendacao_status', title='Status da Recomendação', sort='-x'),
    tooltip=['recomendacao_status', 'count']
).properties(
    title='Status das Recomendações de Segurança Emitidas'
).interactive()

st.altair_chart(chart_recomendacao, use_container_width=True)
st.info(
    "💡 **Insight:** A maioria das recomendações foi **'ADOTADA'** ou **'IMPLEMENTADA'**. "
    "No entanto, existe um volume significativo de recomendações **'AGUARDANDO RESPOSTA'**, "
    "indicando um possível gargalo no *feedback* das agências e operadores."
)
st.markdown("---")


# --- 8. SEÇÃO 6: SOLUÇÕES E RECOMENDAÇÕES ---
st.header("Seção 6: Soluções e Recomendações Estratégicas (Para a ANAC)")
st.markdown("Com base em **toda** a história que os dados contaram, propomos as seguintes ações para aumentar a segurança da aviação:")

rec1, rec2, rec3 = st.columns(3)

with rec1:
    st.subheader("1. 🎯 Foco na Fiscalização")
    st.markdown(
        "A **Aviação Geral (Particular e Agrícola)**, e não a comercial, representa o maior "
        "foco de acidentes (Seção 2). A fiscalização e os programas de prevenção da ANAC "
        "devem ter esse segmento e os **estados do Centro-Oeste (MT, GO)** como prioridade absoluta (Seção 3)."
    )

with rec2:
    st.subheader("2. 🧠 Foco no Treinamento")
    st.markdown(
        "Os principais fatores humanos são **'Julgamento'** e **'Processo Decisório'** (Seção 4), "
        "especialmente durante **'Pouso'** e **'Decolagem'** (Seção 2). "
        "Recomendamos reforço em treinamentos de **CRM** (Gerenciamento de Recursos) e **ADM** (Tomada de Decisão Aeronáutica)."
    )
    
with rec3:
    st.subheader("3. ✈️ Foco no *Feedback*")
    st.markdown(
        "**'Falha do Motor em Voo'** é um evento crítico (Seção 2). Deve-se "
        "reforçar a manutenção preventiva na aviação geral. Além disso, "
        "é preciso cobrar o *feedback* das recomendações **'AGUARDANDO RESPOSTA'** (Seção 5) para fechar o ciclo de segurança."
    )