import pandas as pd
from sqlalchemy import create_engine, text

# Conexão com o banco de dados
db_engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/postgres')

def carregar_dicionario_e_criar_metadados(caminho_dicionario):
    """
    Lê o dicionário de dados do INEP (Excel/CSV) e salva como uma tabela de metadados.
    """
    print("Lendo arquivo de dicionário do INEP...")
    
    # Lendo a partir da segunda linha (header=1) conforme seu padrão
    df_dic = pd.read_excel(caminho_dicionario, header=1)
    
    # Padroniza cabeçalhos do dicionário para minúsculas
    df_dic.columns = [str(col).strip().lower().replace(' ', '_') for col in df_dic.columns]
    
    cols_validas = [col for col in df_dic.columns if not col.startswith('unnamed')]
    df_dic = df_dic[cols_validas].dropna(how='all')
    
    # Salva os metadados no banco
    df_dic.to_sql('metadados_dicionario', con=db_engine, if_exists='replace', index=False)
    print("✓ Tabela 'metadados_dicionario' criada com sucesso!")
    return df_dic

def carregar_microdados(caminho_microdados, nome_tabela, limite_linhas=None):
    """
    Lê o arquivo de microdados (CSV com delimitador ';') e salva no banco de dados.
    """
    print(f"Lendo microdados de {caminho_microdados}...")
    
    df_dados = pd.read_csv(
        caminho_microdados, 
        sep=';', 
        encoding='iso-8859-1', 
        nrows=limite_linhas,
        low_memory=False
    )
    
    # CRÍTICO: Transforma o nome das colunas da tabela de dados para minúsculas
    # para bater com o padrão do Postgres e evitar problemas com aspas
    df_dados.columns = [col.strip().lower() for col in df_dados.columns]
    
    df_dados.to_sql(nome_tabela, con=db_engine, if_exists='replace', index=False)
    print(f"✓ Tabela '{nome_tabela}' populada com {len(df_dados)} registros!")

def aplicar_comentarios_colunas(df_dic, nome_tabela):
    """
    Aplica as descrições do dicionário como comentários nativos nas colunas da tabela.
    """
    print(f"Aplicando comentários nas colunas da tabela '{nome_tabela}'...")
    
    # Identifica as colunas corretas após a conversão para minúsculas realizada na leitura
    col_nome_variavel = 'nome_da_coluna' if 'nome_da_coluna' in df_dic.columns else 'nome_da_variavel'
    col_descricao = 'descricao' if 'descricao' in df_dic.columns else 'descrição'
    
    with db_engine.connect() as conn:
        for _, row in df_dic.iterrows():
            # Força o nome da coluna para minúsculo para bater com a tabela de microdados
            nome_coluna = str(row[col_nome_variavel]).strip().lower()
            descricao = str(row[col_descricao]).replace("'", "''").strip()
            
            # Como as colunas agora são minúsculas, as aspas duplas funcionam perfeitamente
            sql = f'COMMENT ON COLUMN public.{nome_tabela}."{nome_coluna}" IS \'{descricao}\';'
            try:
                conn.execute(text(sql))
            except Exception:
                # Ignora se a coluna mapeada no dicionário não existir na tabela física
                pass
                
        conn.commit()
    print("✓ Comentários das colunas aplicados no PostgreSQL com sucesso!")

if __name__ == '__main__':
    ARQUIVO_DICIONARIO = "dicionário_dados_educação_superior.xlsx"
    ARQUIVO_MICRODADOS = "/home/rafaeldosreisacosta/siac/MICRODADOS_CADASTRO_CURSOS_2024.CSV"
    NOME_TABELA_DADOS = "microdados_ies"
    
    # 1. Carrega o dicionário e retorna o DataFrame tratado
    df_dicionario = carregar_dicionario_e_criar_metadados(ARQUIVO_DICIONARIO)
    
    # 2. Carrega os microdados no banco (com colunas em minúsculo)
    carregar_microdados(ARQUIVO_MICRODADOS, nome_tabela=NOME_TABELA_DADOS, limite_linhas=1000)
    
    # 3. Agora sim, com a tabela criada e dados tratados, aplica os comentários
    aplicar_comentarios_colunas(df_dicionario, nome_tabela=NOME_TABELA_DADOS)
