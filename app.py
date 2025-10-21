import streamlit as st
import pandas as pd
import altair as alt

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard | Segurança de Voo CENIPA",
    layout="wide"
)

# --- 2. CARREGAR E PREPARAR OS DADOS (EM CACHE) ---
# Esta função é executada apenas uma vez para carregar e limpar todos os dados.
@st.cache_data
def load_data():
    """Carrega, limpa e pré-processa todos os 5 arquivos CSV do CENIPA."""
    try:
        # Definir valores que serão tratados como Nulos
        na_values = ['***', 'NULL', 'NA', 'N/A', '']
        
        # --- CORREÇÃO AQUI: Adicionado encoding='latin-1' ---
        
        # Carregar os 5 arquivos com a codificação correta
        df_ocorrencia = pd.read_csv('data/ocorrencia.csv', sep=';', na_values=na_values, low_memory=False, encoding='latin-1')
        df_aeronave = pd.read_csv('data/aeronave.csv', sep=';', na_values=na_values, low_memory=False, encoding='latin-1')
        df_fator = pd.read_csv('data/fator_contribuinte.csv', sep=';', na_values=na_values, low_memory=False, encoding='latin-1')
        df_tipo = pd.read_csv('data/ocorrencia_tipo.csv', sep=';', na_values=na_values, low_memory=False, encoding='latin-1')
        # df_recomendacao = pd.read_csv('data/recomendacao.csv', sep=';', na_values=na_values, low_memory=False, encoding='latin-1') # Carregado mas não usado nos gráficos
        
        # --- Limpeza e Processamento ---
        
        # 1. Tabela OCORRÊNCIA
        # Converter 'ocorrencia_dia' para datetime e extrair o ano
        df_ocorrencia['ocorrencia_dia'] = pd.to_datetime(df_ocorrencia['ocorrencia_dia'], dayfirst=True, errors='coerce')
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_dia'].dt.year
        # Limpar Nulos do ano (se a data falhou)
        df_ocorrencia = df_ocorrencia.dropna(subset=['ocorrencia_ano'])
        df_ocorrencia['ocorrencia_ano'] = df_ocorrencia['ocorrencia_ano'].astype(int)
        
        # 2. Tabela AERONAVE
        # Converter fatalidades para numérico, tratando erros e Nulos
        df_aeronave['aeronave_fatalidades_total'] = pd.to_numeric(df_aeronave['aeronave_fatalidades_total'], errors='coerce').fillna(0)
        # Preencher Nulos no segmento (extremamente importante para a análise)
        df_aeronave['aeronave_registro_segmento'] = df_aeronave['aeronave_registro_segmento'].fillna('INDETERMINADO')

        # 3. Tabela FATOR
        df_fator = df_fator.dropna(subset=['fator_area'])
        
        # 4. Tabela TIPO
        df_tipo = df_tipo.dropna(subset=['ocorrencia_tipo'])
        
        # Retornar um dicionário com os DataFrames limpos
        return {
            "ocorrencia": df_ocorrencia,
            "aeronave": df_aeronave,
            "fator": df_fator,
            "tipo": df_tipo
            # "recomendacao": df_recomendacao
        }

    except FileNotFoundError as e:
        st.error(f"Erro ao carregar os dados. Verifique se o arquivo está no local correto (pasta 'data/'). Detalhe: {e}")
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

# --- 3. SEÇÃO 1: TÍTULO E PANORAMA GERAL ---
st.title("Decolando com Segurança: Onde Reside o Risco Aéreo no Brasil?")
st.warning(
    "**Problemática:** Onde realmente reside o maior risco na aviação civil brasileira? "
    "Nossa análise investiga se o perigo está nas **Máquinas** (falhas mecânicas) ou no **Fator Humano** (decisões e operações)."
)

st.header("Seção 1: O Panorama Geral das Ocorrências")
st.markdown("Primeiro, vamos entender o contexto. Quantas ocorrências temos e qual a gravidade delas?")

# KPIs da Seção 1
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric(
    "Total de Ocorrências (desde 2007)",
    f"{df_ocorrencia.shape[0]:,}"
)
kpi2.metric(
    "Total de Fatalidades (desde 2007)",
    f"{int(df_aeronave['aeronave_fatalidades_total'].sum()):,}"
)
# Gráfico de pizza pequeno para Classificação
classificacao_data = df_ocorrencia['ocorrencia_classificacao'].value_counts().reset_index()
chart_classif = alt.Chart(classificacao_data).mark_arc(outerRadius=80).encode(
    theta=alt.Theta("count", stack=True),
    color=alt.Color("ocorrencia_classificacao", title="Classificação"),
    tooltip=["ocorrencia_classificacao", "count"]
).properties(title="Ocorrências por Classificação")
kpi3.altair_chart(chart_classif)


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

# --- 4. SEÇÃO 2: ONDE ESTÁ O RISCO? (SEGMENTO E TIPO) ---
st.header("Seção 2: Onde o Risco se Concentra?")
st.markdown("""
O público geral teme a aviação comercial (voos de linha aérea), mas será que é ela a principal fonte de risco? 
Aqui, **focamos apenas em ACIDENTES** para entender onde o perigo é maior.
""")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Risco por Segmento da Aviação")
    
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
    st.info("💡 **Insight (Quebra de Mito):** A aviação **PARTICULAR** e **AGRÍCOLA** somam a vasta maioria dos acidentes, não a aviação REGULAR (Linhas Aéreas).")

with col2:
    st.subheader("Tipos de Ocorrências Mais Comuns")
    
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
    st.info("💡 **Insight:** 'FALHA DO MOTOR EM VOO' e 'PERDA DE CONTROLE EM VOO' estão entre os eventos mais comuns e graves.")

st.markdown("---")

# --- 5. SEÇÃO 3: A CAUSA RAIZ (MÁQUINA VS. HOMEM) ---
st.header("Seção 3: A Causa Raiz - Máquina ou Homem?")
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

# --- 6. SEÇÃO 4: SOLUÇÕES E RECOMENDAÇÕES ---
st.header("Seção 4: Soluções e Recomendações Estratégicas (Para a ANAC)")
st.markdown("Com base na história que os dados contaram, propomos as seguintes ações para aumentar a segurança da aviação:")

rec1, rec2, rec3 = st.columns(3)

with rec1:
    st.subheader("1. 🎯 Foco na Fiscalização")
    st.markdown(
        "A **Aviação Geral (Particular e Agrícola)**, e não a comercial, representa o maior "
        "foco de acidentes (Seção 2). A fiscalização e os programas de prevenção da ANAC "
        "devem ter esse segmento como prioridade absoluta."
    )

with rec2:
    st.subheader("2. 🧠 Foco no Treinamento")
    st.markdown(
        "Os principais fatores humanos são **'Julgamento'** e **'Processo Decisório'** (Seção 3). "
        "Isso sugere que os pilotos sabem *como* voar, mas falham em *quando* tomar decisões. "
        "Recomendamos reforço em treinamentos de **CRM** (Gerenciamento de Recursos) e **ADM** (Tomada de Decisão Aeronáutica)."
    )
    
with rec3:
    st.subheader("3. ✈️ Foco no Tipo de Ocorrência")
    st.markdown(
        "**'Falha do Motor em Voo'** é um evento crítico (Seção 2). Deve-se "
        "reforçar a fiscalização de manutenção preventiva (pane seca, contaminação de combustível, etc.) "
        "na aviação geral, onde a manutenção pode ser menos rigorosa que na comercial."
    )