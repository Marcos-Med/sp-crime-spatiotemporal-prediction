// Formato dos dados usados pela página.
export type CodigoMunicipio = string;

export interface AlvoMapa {
  id: string;
  nome: string;
}

export interface HexPrevisao {
  h3: string;
  municipio: CodigoMunicipio;
  risco: Record<string, number[]>;
  imputado?: boolean;
}

export interface ArquivoPrevisoes {
  fonte: 'mock' | 'modelo';
  geradoEm: string;
  resolucaoH3: number;
  unidade: string;
  meses: string[];
  alvos: AlvoMapa[];
  hexagonos: HexPrevisao[];
}

export interface Metricas {
  r2: number | null;
  mae: number | null;
  rmse: number | null;
  pai: number | null;
}

export interface MetadadosMunicipio {
  codigo: CodigoMunicipio;
  nome: string;
  hexagonos: number | null;
  areaKm2: number | null;
  crimes: { total: number; furto: number; roubo: number } | null;
  ipvsMedio: number | null;
  taxaAlfabetizacao: number | null;
  pctJovens15a29: number | null;
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
  nome: string;
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
  importancia: number;
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
    variaveis: Variavel[];
    outras?: { quantidade: number; importancia: number; maior: number; itens: string[] };
    pesoBairro?: number;
  }[];
  todasVariaveis: { grupo: GrupoVariavel; nome: string; itens: string }[];
}
