import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

# 1. Configuração inicial da página
st.set_page_config(page_title="Explorador INEP", layout="wide")
st.title("📊 Painel de Exploração - Microdados INEP")
st.markdown("Interface analítica ligada diretamente ao PostgreSQL local.")

# 2. Ligação à base de dados com Cache (evita reconexões constantes)
@st.cache_resource
def iniciar_conexao():
    return create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/postgres')

engine = iniciar_conexao()

# 3. Menu lateral para escolha da tabela
st.sidebar.header("Controlos")
tabela_selecionada = st.sidebar.selectbox(
    "Escolha a tabela que pretende analisar:",
    ("microdados_ies", "microdados_cursos")
)

limite_linhas = st.sidebar.slider("Número de registos a carregar:", 100, 5000, 1000)

# 4. Funções para carregar os dados
@st.cache_data
def carregar_dados(tabela, limite):
    query = f"SELECT * FROM public.{tabela} LIMIT {limite}"
    return pd.read_sql(query, con=engine)

@st.cache_data
def executar_query(query):
    """Função dedicada para rodar consultas SQL específicas com cache."""
    return pd.read_sql(query, con=engine)

# ==========================================
# NOVA FUNÇÃO DE MAPEAMENTO / TRADUÇÃO
# ==========================================
def aplicar_mapeamentos(df):
    """Recebe um dataframe e traduz as colunas de códigos para texto, se elas existirem."""
    
    mapa_grau_academico = {1: "Bacharelado", 2: "Licenciatura", 3: "Tecnológico", 4: "Bacharelado e Licenciatura"}
    mapa_modalidade = {1: "Presencial", 2: "Curso a distância (EAD)"}
    mapa_organizacao = {1: "Universidade", 2: "Centro Universitário", 3: "Faculdade", 4: "Instituto Federal", 5: "CEFET"}
    mapa_categoria = {1: "Pública Federal", 2: "Pública Estadual", 3: "Pública Municipal", 4: "Privada com fins lucrativos", 5: "Privada sem fins lucrativos", 6: "Privada - Confessional", 7: "Especial"}

    # Verifica se a coluna existe no dataframe atual e traduz
    if "TP_GRAU_ACADEMICO" in df.columns:
        df["TP_GRAU_ACADEMICO"] = pd.to_numeric(df["TP_GRAU_ACADEMICO"], errors='coerce').map(mapa_grau_academico).fillna("Desconhecido")
        
    if "TP_MODALIDADE_ENSINO" in df.columns:
        df["TP_MODALIDADE_ENSINO"] = pd.to_numeric(df["TP_MODALIDADE_ENSINO"], errors='coerce').map(mapa_modalidade).fillna("Desconhecido")
        
    if "TP_ORGANIZACAO_ACADEMICA" in df.columns:
        df["TP_ORGANIZACAO_ACADEMICA"] = pd.to_numeric(df["TP_ORGANIZACAO_ACADEMICA"], errors='coerce').map(mapa_organizacao).fillna("Desconhecido")
        
    if "TP_CATEGORIA_ADMINISTRATIVA" in df.columns:
        df["TP_CATEGORIA_ADMINISTRATIVA"] = pd.to_numeric(df["TP_CATEGORIA_ADMINISTRATIVA"], errors='coerce').map(mapa_categoria).fillna("Desconhecido")
        
    return df
# ==========================================


# Organizando a interface em Abas (Tabs) para separar as visões
aba1, aba2 = st.tabs(["🔍 Exploração Geral", "📈 Relatórios Específicos (Insights)"])

with aba1:
    # 5. Apresentação dos dados e gráficos gerais
    try:
        with st.spinner(f"A extrair dados de {tabela_selecionada}..."):
            df = carregar_dados(tabela_selecionada, limite_linhas)
            
            # ---> APLICA A TRADUÇÃO AQUI NA TABELA GERAL <---
            df = aplicar_mapeamentos(df)
        
        st.write(f"### Pré-visualização da Tabela ({len(df)} registos)")
        # Mostra a grelha de dados interativa
        st.dataframe(df, use_container_width=True)

        st.divider()

        # 6. Módulo de Análise e Gráficos Rápidos
        st.write("### Análise de Distribuição")
        coluna_grafico = st.selectbox(
            "Selecione uma coluna para visualizar a contagem de ocorrências:", 
            df.columns
        )
        
        # Prepara os dados para o gráfico de barras
        if coluna_grafico:
            contagem = df[coluna_grafico].value_counts().reset_index()
            contagem.columns = [coluna_grafico, 'Quantidade']
            st.bar_chart(contagem, x=coluna_grafico, y='Quantidade')

    except Exception as e:
        st.error(f"Erro ao carregar os dados gerais. Verifique se o PostgreSQL está ativo. Detalhe: {e}")


with aba2:
    st.write("### Consultas Predefinidas do INEP")
    st.markdown("Resultados agregados diretamente da base de dados PostgreSQL.")
    
    try:
        # --- Consulta 1 ---
        st.write("#### 1. Cursos por Grau Acadêmico e Modalidade de Ensino")
        query_1 = """
        SELECT 
            "TP_GRAU_ACADEMICO", 
            "TP_MODALIDADE_ENSINO", 
            COUNT(*) AS total_cursos
        FROM public.microdados_cursos
        GROUP BY "TP_GRAU_ACADEMICO", "TP_MODALIDADE_ENSINO"
        ORDER BY total_cursos DESC;
        """
        df_q1 = executar_query(query_1)
        
        # ---> APLICA A TRADUÇÃO AQUI NA CONSULTA 1 <---
        df_q1 = aplicar_mapeamentos(df_q1)
        
        st.dataframe(df_q1, use_container_width=True)

        st.divider()

        # --- Consulta 2 ---
        st.write("#### 2. Top 15 IES por Quantidade de Cursos Ofertados")
        query_2 = """
        SELECT 
            i."NO_IES",
            COUNT(c."CO_CURSO") as total_cursos_ofertados
        FROM public.microdados_ies i
        JOIN public.microdados_cursos c ON i."CO_IES" = c."CO_IES"
        GROUP BY i."CO_IES", i."NO_IES"
        ORDER BY total_cursos_ofertados DESC
        LIMIT 15;
        """
        df_q2 = executar_query(query_2)
        st.dataframe(df_q2, use_container_width=True)
        
        # Como o NO_IES já é um texto (nome da faculdade), não precisamos converter para string
        st.bar_chart(df_q2, x="NO_IES", y="total_cursos_ofertados")

        st.divider()

        # --- Consulta 3 ---
        st.write("#### 3. Quantidade de IES por Categoria Administrativa")
        query_3 = """
        SELECT 
            "TP_CATEGORIA_ADMINISTRATIVA", 
            COUNT(*) AS quantidade_ies
        FROM public.microdados_ies
        GROUP BY "TP_CATEGORIA_ADMINISTRATIVA"
        ORDER BY quantidade_ies DESC;
        """
        df_q3 = executar_query(query_3)
        
        # ---> APLICA A TRADUÇÃO AQUI NA CONSULTA 3 <---
        df_q3 = aplicar_mapeamentos(df_q3)
        
        st.dataframe(df_q3, use_container_width=True)
        # O gráfico agora usará os nomes traduzidos!
        st.bar_chart(df_q3, x="TP_CATEGORIA_ADMINISTRATIVA", y="quantidade_ies")

    except Exception as e:
        st.error(f"Erro ao executar as consultas específicas. Detalhe: {e}")