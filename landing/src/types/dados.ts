// Formato dos dados que a página espera receber.
// Ao trocar o mock pelo modelo real, mantenha estes formatos.

export type CodigoMunicipio = string; // código IBGE de 7 dígitos (ex.: "3550308")

export interface AlvoMapa {
  id: string; // "crime" (furto + roubo), "furto" ou "roubo", os mesmos ids de metricas.json
  nome: string;
}

export interface HexPrevisao {
  h3: string; // índice H3 do hexágono
  municipio: CodigoMunicipio;
  // nota de risco de 0 a 1 por tipo de crime: um valor por mês, na mesma ordem de `meses`
  risco: Record<string, number[]>;
  // true = a célula recebeu as ocorrências sem endereço exato da cidade (mediana das coordenadas), o que infla a nota
  imputado?: boolean;
}

export interface ArquivoPrevisoes {
  fonte: 'mock' | 'modelo';
  geradoEm: string;
  resolucaoH3: number;
  unidade: string;
  meses: string[]; // "AAAA-MM", em ordem
  alvos: AlvoMapa[];
  hexagonos: HexPrevisao[];
}

export interface Metricas {
  r2: number | null; // null = ainda não calculado
  mae: number | null;
  rmse: number | null;
  pai: number | null;
}

// Dados por município, tirados da base do Marcos (datasets/database_processed_h3_final.csv)
// por scripts/gerar-municipios.py. Campo null = ainda não carregado.
// Os dados do Censo no modelo são médias dos setores censitários de cada hexágono, por isso
// aqui só entram médias (IPVS, alfabetização, jovens) e não totais como a população do município.
export interface MetadadosMunicipio {
  codigo: CodigoMunicipio;
  nome: string;
  hexagonos: number | null; // hexágonos do município mostrados no mapa (sem as células fora da RMSP)
  areaKm2: number | null; // área coberta por esses hexágonos
  crimes: { total: number; furto: number; roubo: number } | null; // registrados de jan/2022 a jun/2026
  ipvsMedio: number | null; // média do grupo IPVS (C_IPVS) dos hexágonos
  taxaAlfabetizacao: number | null; // %, média dos hexágonos
  pctJovens15a29: number | null; // %, média dos hexágonos
}

export interface ModeloComparado {
  id?: string;
  nome: string;
  descricao?: string;
  principal?: boolean;
  metricas: Metricas;
}

export interface AlvoMetricas {
  id?: string;
  nome: string; // "Crime total", "Furto", "Roubo"
  /** % de RMSE a menos que cada referência (artigo final, tabelas de validação e teste) */
  ganhos?: { testeEwm3: number; testeMediaFixa: number; validacaoEwm3: number };
  modelos: ModeloComparado[];
}

export interface ArquivoMetricas {
  fonte: string;
  status: 'validacao' | 'teste';
  observacao?: string;
  escala: string;
  periodoValidacao: { inicio: string; fim: string };
  periodoTeste: { inicio: string; fim: string };
  testeDisponivel: boolean;
  alvos: AlvoMetricas[];
  tabelasExtras?: { titulo: string; descricao: string; alvos: AlvoMetricas[] }[];
}

export type GrupoVariavel = 'historico' | 'vizinhanca' | 'calendario' | 'territorio' | 'social';

export interface Variavel {
  id: string;
  nome: string;
  grupo: GrupoVariavel;
  importancia: number; // fração de 0 a 1 entre as variáveis mostradas
  valorOriginal?: number;
  explicacao: string;
}

export interface ArquivoVariaveis {
  fonte: string;
  observacao?: string;
  alvos: {
    id: string;
    nome: string;
    modelo?: string;
    variaveis: Variavel[]; // importancia = parte do peso TOTAL do modelo
    outras?: { quantidade: number; importancia: number; maior: number; itens: string[] }; // variáveis não mostradas
    pesoBairro?: number; // Censo + IPVS somados, fração do peso total
  }[];
  todasVariaveis: { grupo: GrupoVariavel; nome: string; itens: string }[];
}
