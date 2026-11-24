// Cores do mapa: divide as notas em cinco faixas de risco.
export const CORES_RISCO = ['#fbe3a1', '#f6ad55', '#e8663a', '#bf2f4c', '#5f1a55'];
export const NOMES_RISCO = ['Muito baixo', 'Baixo', 'Médio', 'Alto', 'Muito alto'];
const QUANTIS = [0.4, 0.7, 0.88, 0.97];

export function calcularCortes(valores: Float64Array): number[] {
  const ord = Float64Array.from(valores).sort();
  const cortes = QUANTIS.map((q) => ord[Math.min(ord.length - 1, Math.floor(q * ord.length))]);
  if (cortes[0] <= 0) cortes[0] = 0.0005;
  for (let i = 1; i < cortes.length; i++) if (cortes[i] <= cortes[i - 1]) cortes[i] = cortes[i - 1] + 1e-6;
  return cortes;
}

export function classeDe(v: number, cortes: number[]): number {
  let c = 0;
  while (c < cortes.length && v >= cortes[c]) c++;
  return c;
}

export const fmt = (v: number, casas = 0) =>
  v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
