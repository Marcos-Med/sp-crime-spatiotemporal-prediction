# Mapa de Risco SP · Landing page do projeto RP2

Landing page do projeto de previsão de crimes na Grande São Paulo (risco por hexágono H3, modelos Random Forest e GAM).

## Como executar

### Opção 1: só ver a página (sem instalar nada)

Baixe e abra `landing-rp2-pronto.html` com dois cliques, em qualquer navegador atual. É a página já compilada num
arquivo só. Precisa de internet apenas para o mapa de fundo (ruas e nomes) e as fontes; sem ela, o restante funciona.

### Opção 2: rodar o código

1. Instale o [Node.js](https://nodejs.org) 18 ou 20+ (confira com `node -v`).
2. Baixe o projeto (botão **Code → Download ZIP** no GitHub, ou `git clone <link do repositório>`).
3. Abra um terminal na pasta do projeto, a que tem o `package.json`, e rode:

```bash
npm install
npm run dev
```

4. Abra http://localhost:5173 no navegador. Para parar, aperte `Ctrl + C` no terminal.

Os dados já estão em `src/data/`: não precisa de Python nem dos CSVs para executar.

### Comandos

| Comando | O que faz |
|---|---|
| `npm install` | instala as dependências (só na primeira vez) |
| `npm run dev` | abre a página em modo de desenvolvimento, atualizando a cada mudança |
| `npm run build` | confere os tipos e gera o site pronto em `dist/` |
| `npm run preview` | serve o `dist/` localmente (rode o `build` antes) |
| `npm run arquivo-unico` | gera de novo o `landing-rp2-pronto.html` (rode o `build` antes) |

### Problemas comuns

- **Página em branco ao abrir o `index.html`:** ele é o código-fonte. Use a opção 1 ou `npm run dev`.
- **Porta 5173 ocupada:** o Vite escolhe outra e mostra o endereço no terminal.
- **`npm` não é reconhecido:** instale o Node.js e abra um terminal novo.

### Publicar

A pasta `dist/` é um site estático: pode ir para GitHub Pages, Vercel, Netlify ou qualquer servidor.

## De onde vêm os dados (artigo final enviado; dados do commit b5f59f5, 22/11/2026)

Tudo na página é real e vem do repositório do Marcos (`Marcos-Med/sp-crime-spatiotemporal-prediction`): do artigo
`Template_SBC/template-latex/Artigo_Pesquisa.tex` e dos CSVs da pasta `datasets/` (fora do GitHub, compartilhados
pelo Drive do grupo).

| Parte da página | Origem |
|---|---|
| Previsões por hexágono no mapa (nota de 0 a 1 por mês, 1.208 hexágonos, jul/2025–jun/2026) | `final_model_comparison_groups_h3_predictions.csv` (`particao == "teste_reservado"`), modelo escolhido na validação: RF resíduo para crime e furto, GAM resíduo para roubo |
| R², MAE e RMSE do teste (modelo final e referências) | `final_model_comparison_groups_h3_summary.csv` (`avaliacao == "teste_reservado"`) |
| Seção Resultados: ganhos por tipo de crime (`ganhos` em `metricas.json`) e as quatro respostas | artigo final (tabelas de validação e teste, mapas e conclusão), copiado à mão; `gerar-previsoes.py` não altera |
| PAI do teste e da validação (não está no artigo e não aparece na página) | calculado por `scripts/gerar-previsoes.py`: 5% de hexágonos com maior nota em cada mês, média dos meses (12 no teste, 18 na validação) |
| Métricas da validação jan/2024–jun/2025 | artigo e `validation_target_specific_residual_h3` |
| Importância das variáveis | `final_model_comparison_groups_h3_ebm_importance.csv` (`avaliacao == "treino_final"`), modelos finais RF/GAM; porcentagem do peso total do modelo, com as demais somadas em "Outras N variáveis"; seno e cosseno do mês somados em "Época do ano" |
| Números da base (2,59 mi furtos e roubos de 5,35 mi boletins, 1.260 hexágonos, 11% sem coordenada, 70% em 10%) | notebooks de processamento e análise exploratória |
| Dados por município (ocorrências, hexágonos, área, IPVS, alfabetização, jovens) | `scripts/gerar-municipios.py` + `database_processed_h3_final.csv` |

Santa Isabel não tem nenhum hexágono na base do modelo, então aparece sem dados.

**Células fora da região.** O modelo usa 1.260 células, mas 52 delas ficam no interior do estado: a base filtra a
RMSP pelo nome da cidade do boletim, e algumas coordenadas foram geocodificadas em outro município (por exemplo,
boletins de "S.PAULO" com coordenada em Glicério, perto de Araçatuba). Elas somam 89 ocorrências (0,003%). Os scripts
tiram essas células do mapa e do painel dos municípios (`dentro_da_rmsp` em `gerar-municipios.py`), então a página
mostra 1.208 hexágonos. As métricas (R², MAE, RMSE, PAI) continuam calculadas sobre as 1.260 células, como no artigo.
Os scripts precisam de `shapely`, além de `pandas` e `h3`.

**Ocorrências sem endereço.** O pipeline põe os registros sem coordenada na mediana das coordenadas da cidade. A célula
desse ponto fica com a nota inflada (na capital, um único ponto tem 307 mil ocorrências, 79% da célula, e é a nota mais
alta do mapa). `gerar-previsoes.py` marca essas células com `"imputado": true` usando `database_processed_h3.csv`;
o destaque do topo as ignora e a dica do mapa avisa quando o mouse está sobre uma delas.

## Tecnologias

React 18 + TypeScript + Vite, MapLibre GL (mapa gratuito) e h3-js (hexágonos H3).

## Seções

1. **Hero e "O projeto"**: explicação em linguagem simples e arte com os hexágonos do Centro.
2. **Mapa de risco preditivo**: filtros de tipo de crime (crime total, furto, roubo), período (mês, ano, 12 meses) e município. Clique em um município para dar zoom;
   clique de novo nele para abrir o painel com os metadados.
3. **Resultados**: ganhos por tipo de crime e as quatro respostas do artigo.
4. **Explicabilidade**: peso de cada variável e comparação com as referências (média do hexágono,
   média recente) em R², MAE e RMSE.
5. **Limitações e cuidados**, com os próximos passos.

## Dados por município

O painel do município mostra só dados reais da base do Marcos: furtos e roubos registrados (jan/2022 a jun/2026),
hexágonos no modelo, área coberta, IPVS médio, alfabetização e % de jovens de 15 a 29 anos.
Não mostra população nem domicílios porque, na base do modelo, os dados do Censo de cada hexágono são **médias** dos
setores censitários com ocorrência (`creating_features_ssp_sp.ipynb`); somá-los não daria a população do município.

Para carregar (precisa de Python com `pandas` e `h3`):

```bash
python scripts/gerar-municipios.py "<repo do Marcos>/datasets/database_processed_h3_final.csv"
```

O CSV sai de `processing_datasets/creating_features_ssp_sp.ipynb` e fica em `datasets/`, fora do GitHub.

## Como gerar os dados de novo

Com os CSVs do Marcos em `<repo>/datasets/` (precisa de Python com `pandas` e `h3`):

```bash
python scripts/gerar-municipios.py "<repo do Marcos>/datasets/database_processed_h3_final.csv"
python scripts/gerar-previsoes.py "<repo do Marcos>/datasets"
npm run build && npm run arquivo-unico
```

`gerar-previsoes.py` escreve `src/data/previsoes.json` e atualiza R², MAE, RMSE e PAI do teste em `src/data/metricas.json`.
O formato de cada arquivo está descrito em `src/types/dados.ts`.

| Arquivo | O que é | Formato |
|---|---|---|
| `previsoes.json` | nota de risco por hexágono, tipo de crime e mês | `meses[]` ("AAAA-MM") + `alvos[]` (`crime`, `furto`, `roubo`) + `hexagonos[]` com `h3`, `municipio` (código IBGE) e `risco` (`{ crime: [...], furto: [...], roubo: [...] }`, um valor por mês, na ordem de `meses`) |
| `municipios.json` | dados reais de cada município (painel do 2º clique), gerados por `python scripts/gerar-municipios.py <repo do Marcos>/datasets/database_processed_h3_final.csv` | lista de `MetadadosMunicipio`; campos `null` = ainda não carregado |
| `variaveis.json` | importância das variáveis (soma = 1) | lista de `Variavel` com `grupo`: historico, calendario, territorio ou social |
| `metricas.json` | R², MAE, RMSE e PAI do modelo e das referências | lista `modelos[]`; marque o modelo do projeto com `"principal": true` |

Se preferir servir os dados por uma API, troque só o corpo das funções em `src/services/api.ts`
(por exemplo, `fetch('https://sua-api/previsoes')`). Nenhum componente lê os JSON direto.

### Como os filtros de tempo funcionam

O modelo prevê, para cada hexágono e mês, uma nota de risco `r = c / (c + K)`, em que `c` é o número de crimes e `K`
é o percentil 90 das contagens positivas do treino. A nota vai de 0 a 1 e não é probabilidade nem contagem. Por isso
os períodos usam **média**, nunca soma. Em `src/lib/periodo.ts`:

- **Mês**: a nota daquele mês.
- **Ano**: média das notas dos meses daquele ano dentro do período de teste (2025 = jul a dez, 2026 = jan a jun).
- **12 meses**: média de todo o período de teste.

### Outros ajustes

- `src/lib/config.ts`: liga um mapa de fundo com ruas (ex.: OpenFreeMap) e muda o centro e o zoom iniciais.
- `src/lib/cores.ts`: cores e cortes das 5 classes de risco (hoje por quantis: 40%, 70%, 88%, 97%).
- `src/geo/rmsp-municipios.json`: contornos dos 39 municípios (IBGE, simplificados). Não é mock.
- `npm run mock`: gera previsões fictícias para testar o layout. **Atenção:** sobrescreve o `previsoes.json` real; para voltar, rode `gerar-previsoes.py` de novo.

## Estrutura

```
src/geo/           contornos dos municípios (IBGE, não é mock)
scripts/           geradores dos dados reais (previsões, métricas, municípios) e do mock de teste
src/data/          dados da página (gerados pelos scripts)
src/services/      api.ts, único ponto de acesso aos dados
src/types/         formato esperado dos dados
src/lib/           períodos, cores, configuração
src/components/    seções da página (mapa/ tem mapa, filtros e painel)
src/styles/        CSS global (tema claro e escuro)
```
