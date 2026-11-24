// ÚNICO ponto de acesso aos dados da página.
// Lê os JSON de src/data/, gerados a partir dos resultados do modelo (scripts/gerar-previsoes.py e
// scripts/gerar-municipios.py). Para servir por uma API, troque o corpo destas funções, por exemplo:
//       const r = await fetch(`${API_URL}/previsoes`); return r.json();
// O resto da página não precisa mudar.

import type {
  ArquivoMetricas,
  ArquivoPrevisoes,
  ArquivoVariaveis,
  CodigoMunicipio,
  MetadadosMunicipio,
} from '../types/dados';
import previsoes from '../data/previsoes.json';
import municipios from '../data/municipios.json';
import variaveis from '../data/variaveis.json';
import metricas from '../data/metricas.json';
import contornos from '../geo/rmsp-municipios.json';

export const USANDO_MOCK = (previsoes as ArquivoPrevisoes).fonte === 'mock';

export async function buscarPrevisoes(): Promise<ArquivoPrevisoes> {
  return previsoes as ArquivoPrevisoes;
}

export async function buscarMunicipios(): Promise<MetadadosMunicipio[]> {
  return municipios as MetadadosMunicipio[];
}

export async function buscarMetadadosMunicipio(codigo: CodigoMunicipio): Promise<MetadadosMunicipio | undefined> {
  return (municipios as MetadadosMunicipio[]).find((m) => m.codigo === codigo);
}

export async function buscarVariaveis(): Promise<ArquivoVariaveis> {
  return variaveis as ArquivoVariaveis;
}

export async function buscarMetricas(): Promise<ArquivoMetricas> {
  return metricas as ArquivoMetricas;
}

// Contornos dos 39 municípios da Região Metropolitana de São Paulo (não é mock).
export async function buscarContornosMunicipios(): Promise<GeoJSON.FeatureCollection> {
  return contornos as GeoJSON.FeatureCollection;
}
