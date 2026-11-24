// Filtro de tempo: nota do mês ou média do ano ou dos 12 meses.
import type { ArquivoPrevisoes } from '../types/dados';

export type TipoFiltro = 'mes' | 'ano' | 'tudo';
export interface FiltroTempo {
  tipo: TipoFiltro;
  mes: string;
  ano: number;
}

export function mesesDoFiltro(meses: string[], f: FiltroTempo): number[] {
  if (f.tipo === 'mes') return meses.flatMap((m, i) => (m === f.mes ? [i] : []));
  if (f.tipo === 'ano') return meses.flatMap((m, i) => (m.startsWith(String(f.ano)) ? [i] : []));
  return meses.map((_, i) => i);
}

export function valoresDoFiltro(dados: ArquivoPrevisoes, alvo: string, f: FiltroTempo): Float64Array {
  const sel = mesesDoFiltro(dados.meses, f);
  const out = new Float64Array(dados.hexagonos.length);
  if (!sel.length) return out;
  dados.hexagonos.forEach((h, i) => {
    const r = h.risco[alvo];
    let s = 0;
    for (const idx of sel) s += r[idx];
    out[i] = s / sel.length;
  });
  return out;
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
export const nomeMes = (mes: string) => {
  const [a, m] = mes.split('-').map(Number);
  return `${MESES[m - 1]} de ${a}`;
};
export const mesCurto = (mes: string) => `${MESES[Number(mes.slice(5, 7)) - 1].slice(0, 3)}/${mes.slice(0, 4)}`;

export function descreverFiltro(f: FiltroTempo, meses: string[]): string {
  if (f.tipo === 'mes') return nomeMes(f.mes);
  if (f.tipo === 'tudo') return `média de ${mesCurto(meses[0])} a ${mesCurto(meses[meses.length - 1])}`;
  const ms = meses.filter((m) => m.startsWith(String(f.ano)));
  if (!ms.length) return String(f.ano);
  const ini = Number(ms[0].slice(5, 7)), fim = Number(ms[ms.length - 1].slice(5, 7));
  return `média de ${f.ano} (${MESES[ini - 1].slice(0, 3)} a ${MESES[fim - 1].slice(0, 3)})`;
}

export function anosDisponiveis(meses: string[]): number[] {
  return [...new Set(meses.map((m) => Number(m.slice(0, 4))))];
}

export const AVISO_PRECISAO: Record<TipoFiltro, string> = {
  mes: 'O modelo prevê um mês por vez, usando o que aconteceu até o mês anterior.',
  ano: 'Média das notas dos meses daquele ano dentro do período de teste (2025 = jul a dez, 2026 = jan a jun). Bom para comparar regiões.',
  tudo: 'Média das notas dos 12 meses do teste. Mostra onde o risco ficou alto de forma persistente.',
};

export const SOBRE_A_NOTA =
  'A nota vai de 0 a 1 e cresce com o número de crimes esperado no hexágono naquele mês. Ela chega a 0,5 quando esse ' +
  'número é igual ao percentil 90 dos meses com pelo menos um crime no treino (um valor para cada tipo de crime). ' +
  'Não é uma probabilidade nem o número de crimes: serve para comparar lugares e meses.';
