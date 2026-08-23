# Modelagem Preditiva de Manchas Criminais (RMSP)

Repositório destinado ao estudo, processamento de dados e modelagem preditiva espaço-temporal de roubos na Região Metropolitana de São Paulo (RMSP), integrando técnicas de Machine Learning e variáveis socioeconômicas.

---

## 📌 Visão Geral do Repositório

Este projeto realiza a ingestão, limpeza, padronização e unificação dos microdados de ocorrências criminais disponibilizados pela **Secretaria de Segurança Pública do Estado de São Paulo (SSP-SP)**.

Devido às restrições de tamanho de arquivo do GitHub (os conjuntos de dados brutos e processados possuem múltiplos gigabytes), **as bases de dados não são armazenadas diretamente neste repositório**.

---

## 🛠️ Processamento de Dados (`processing_datasets_ssp_sp.ipynb`)

O notebook [`processing_datasets_ssp_sp.ipynb`](./processing_datasets_ssp_sp.ipynb) é responsável por todo o pipeline de ETL (*Extract, Transform, Load*):

1. **Ingestão e Consolidação:** Leitura das tabelas brutas por ano/período provenientes da SSP-SP.
2. **Padronização e Limpeza:** Tratamento de valores nulos, conversão de tipos de dados e padronização das tipologias de crimes (foco em roubos e seus subtipos).
3. **Georreferenciamento:** Limpeza e validação de coordenadas geográficas (latitude e longitude) na RMSP.
4. **Geração da Base Unificada:** Exportação do dataset consolidado pronto para modelagem espaço-temporal e análise estatística.

---

## 📂 Acesso aos Datasets (Google Drive)

A base de dados unificada final, assim como os dados brutos utilizados pelo notebook, encontram-se hospedados e organizados no Google Drive:

👉 **[Acessar pasta dos dados no Google Drive](https://drive.google.com/drive/folders/1cj3oBSGpWeuDevl3gwHo7vAbUyHo4SzK?usp=sharing)**

### Como utilizar os dados localmente:
1. Acesse o link do Google Drive acima.
2. Faça o download do arquivo da base unificada (ou dos dados brutos).
3. Crie uma pasta chamada `data/` na raiz deste repositório.
4. Mova os arquivos baixados para a pasta `data/` (esta pasta já está configurada no `.gitignore` e não será enviada ao GitHub).

---

## 🚀 Como Executar o Notebook

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/SEU-USUARIO/sp-crime-spatiotemporal-prediction.git
   cd sp-crime-spatiotemporal-prediction
   ```

2. **Instale as dependências (recomendado usar ambiente virtual):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Abra e execute o Jupyter Notebook:**
   ```bash
   jupyter notebook processing_datasets_ssp_sp.ipynb
   ```
