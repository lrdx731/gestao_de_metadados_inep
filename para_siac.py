import pandas as pd
from sqlalchemy import create_engine, text

db_engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/postgres')

def carregar_microdados(caminho_microdados, nome_tabela, limite_linhas=None):
    print(f"Lendo microdados de {caminho_microdados}...")
    
    # 1. Lê o CSV permitindo inferência de tipos pelo Pandas
    df_dados = pd.read_csv(
        caminho_microdados, 
        sep=';', 
        encoding='iso-8859-1', 
        nrows=limite_linhas,
        low_memory=False
    )
    
    # 2. Garante que colunas que começam com 'NO_', 'SG_', 'DS_' ou 'CO_' de texto não virem float incorretamente
    cols_texto = [c for c in df_dados.columns if any(c.startswith(prefix) for prefix in ['NO_', 'SG_', 'DS_', 'TX_'])]
    for col in cols_texto:
        df_dados[col] = df_dados[col].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})
    
    # 3. Salva no PostgreSQL
    df_dados.to_sql(nome_tabela, con=db_engine, if_exists='replace', index=False)
    print(f"✓ Tabela '{nome_tabela}' criada com sucesso ({len(df_dados)} registros)!")

def carregar_dicionario_e_criar_metadados(caminho_dicionario):
    print("Lendo arquivo de dicionário do INEP...")
    df_dic = pd.read_excel(caminho_dicionario, sheet_name=0, header=1)
    df_dic_limpo = df_dic.copy()
    df_dic_limpo.columns = [str(col).strip().lower().replace(' ', '_') for col in df_dic_limpo.columns]
    cols_validas = [col for col in df_dic_limpo.columns if not col.startswith('unnamed')]
    df_dic_limpo = df_dic_limpo[cols_validas].dropna(how='all')
    df_dic_limpo.to_sql('metadados_dicionario', con=db_engine, if_exists='replace', index=False)
    print("✓ Tabela 'metadados_dicionario' criada no banco!")

def aplicar_comentarios_no_postgres(caminho_dicionario, nome_tabela):
    print(f"Aplicando descrições nas colunas da tabela '{nome_tabela}'...")
    xl = pd.ExcelFile(caminho_dicionario)
    comentarios_aplicados = 0

    with db_engine.connect() as conn:
        res = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{nome_tabela}';"))
        colunas_postgres = {row[0].upper(): row[0] for row in res}

    if not colunas_postgres:
        print(f"⚠ Tabela '{nome_tabela}' não foi encontrada no banco.")
        return

    with db_engine.connect() as conn:
        for sheet in xl.sheet_names:
            df_raw = pd.read_excel(xl, sheet_name=sheet, header=None)
            idx_header = None
            for idx, row in df_raw.iterrows():
                row_vals = [str(val).lower().strip() for val in row.values if pd.notna(val)]
                has_nome = any(any(k in v for k in ['nome', 'variáv', 'variav', 'campo', 'coluna']) for v in row_vals)
                has_desc = any(any(k in v for k in ['descri', 'conceito', 'significado', 'rótulo', 'rotulo']) for v in row_vals)
                if has_nome and has_desc:
                    idx_header = idx
                    break
            
            if idx_header is not None:
                df_headers = pd.read_excel(xl, sheet_name=sheet, header=idx_header)
                col_nome = next((c for c in df_headers.columns if any(k in str(c).lower() for k in ['nome', 'variáv', 'variav', 'campo', 'coluna'])), None)
                col_desc = next((c for c in df_headers.columns if any(k in str(c).lower() for k in ['descri', 'conceito', 'significado', 'rótulo', 'rotulo'])), None)
                
                if col_nome and col_desc:
                    for _, row in df_headers.iterrows():
                        if pd.isna(row[col_nome]) or pd.isna(row[col_desc]):
                            continue
                        nome_var_excel = str(row[col_nome]).strip()
                        desc_text = str(row[col_desc]).strip()
                        nome_var_upper = nome_var_excel.upper()
                        if nome_var_upper in colunas_postgres:
                            col_real = colunas_postgres[nome_var_upper]
                            desc_escapada = desc_text.replace("'", "''")
                            sql = f'COMMENT ON COLUMN public.{nome_tabela}."{col_real}" IS \'{desc_escapada}\';'
                            conn.execute(text(sql))
                            comentarios_aplicados += 1
        conn.commit()
    print(f"✓ {comentarios_aplicados} descrições aplicadas na tabela '{nome_tabela}'!")

if __name__ == '__main__':
    ARQUIVO_DICIONARIO = "dicionário_dados_educação_superior.xlsx"
    ARQUIVO_IES = "/home/rafaeldosreisacosta/siac/MICRODADOS_CADASTRO_IES_2024.CSV"
    ARQUIVO_CURSOS = "/home/rafaeldosreisacosta/siac/MICRODADOS_CADASTRO_CURSOS_2024.CSV"
    
    carregar_microdados(ARQUIVO_IES, nome_tabela='microdados_ies', limite_linhas=5000)
    carregar_microdados(ARQUIVO_CURSOS, nome_tabela='microdados_cursos', limite_linhas=5000)
    carregar_dicionario_e_criar_metadados(ARQUIVO_DICIONARIO)
    
    aplicar_comentarios_no_postgres(ARQUIVO_DICIONARIO, nome_tabela='microdados_ies')
    aplicar_comentarios_no_postgres(ARQUIVO_DICIONARIO, nome_tabela='microdados_cursos')