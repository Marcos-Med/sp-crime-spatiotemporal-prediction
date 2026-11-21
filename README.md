# Modelagem Preditiva de Manchas Criminais (RMSP)

O objetivo deste projeto é desenvolver um modelo preditivo para estimar o risco de ocorrência de **roubos** na **Região Metropolitana de São Paulo (RMSP)** em determinadas janelas temporais.

## ⚙️ Funcionalidades
- **Visualização Geoespacial:** O modelo será integrado a uma interface de mapa interativo, permitindo a visualização de manchas criminais.
- **Granularidade do Risco:** A plataforma apresentará tanto o índice de risco geral de roubos quanto indicadores segmentados por subtipos específicos da infração.

---

## 🛠️ Processamento de Dados (`processing_datasets_ssp_sp.ipynb`)

Devido às restrições de tamanho de arquivo do GitHub (os conjuntos de dados brutos e processados possuem múltiplos gigabytes), **as bases de dados não são armazenadas diretamente neste repositório**.

O notebook [`processing_datasets_ssp_sp.ipynb`](./processing_datasets_ssp_sp.ipynb) é responsável por todo o pipeline de ETL (*Extract, Transform, Load*):

1. **Ingestão e Consolidação:** Leitura das tabelas brutas por ano/período provenientes da SSP-SP.
2. **Padronização e Limpeza:** Tratamento de valores nulos, conversão de tipos de dados e padronização das tipologias de crimes (foco em roubos e seus subtipos).
3. **Georreferenciamento:** Limpeza e validação de coordenadas geográficas (latitude e longitude) na RMSP.
4. **Feature Engeneering:** Geração de variáveis associadas ao risco de roubo.
5. **Geração da Base Unificada:** Exportação do dataset consolidado pronto para modelagem espaço-temporal e análise estatística.

---

## 📂 Acesso aos Datasets (Google Drive)

A base de dados unificada final, assim como os dados brutos utilizados pelo notebook, encontram-se hospedados e organizados no Google Drive:

👉 **[Acessar pasta dos dados no Google Drive](https://drive.google.com/drive/folders/1cj3oBSGpWeuDevl3gwHo7vAbUyHo4SzK?usp=sharing)**

### Como utilizar os dados localmente:
1. Acesse o link do Google Drive acima.
2. Faça o download do arquivo da base unificada (ou dos dados brutos).
3. Crie a pasta `datasets/` na raiz do repositório.
4. Coloque os arquivos criminais da SSP-SP em `datasets/SSP-SP/` e mantenha as fontes socioeconômicas em `datasets/CENSO_IBGE_2022/` e `datasets/IPVS_2022/`. A pasta `datasets/` está no `.gitignore` e não será enviada ao GitHub.

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
   jupyter notebook processing_datasets/processing_datasets_ssp_sp.ipynb
   ```

## 📊 Dashboard dos Resultados

Depois de executar a comparação final (que também ajusta os modelos selecionados e testa o período reservado), instale as dependências do painel e inicie o Streamlit na raiz do repositório:

```bash
pip install -r requirements-dashboard.txt
streamlit run processing_datasets/dashboard_resultados_ssp_sp.py
```

O painel lê os CSVs já gerados em `datasets/`; ele não executa notebooks nem treina modelos. A aba **Teste reservado** mostra jul/2025–jun/2026. A aba **Explicabilidade** mostra somente o modelo final escolhido para o alvo selecionado.
