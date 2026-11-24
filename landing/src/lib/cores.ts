// Escala de cor do risco: 5 classes por quantis do período escolhido.
export const CORES_RISCO = ['#fbe3a1', '#f6ad55', '#e8663a', '#bf2f4c', '#5f1a55'];
export const NOMES_RISCO = ['Muito baixo', 'Baixo', 'Médio', 'Alto', 'Muito alto'];
// Cortes nos quantis: 40%, 70%, 88%, 97% dos hexágonos
const QUANTIS = [0.4, 0.7, 0.88, 0.97];

export function calcularCortes(valores: Float64Array): number[] {
  const ord = Float64Array.from(valores).sort();
  const cortes = QUANTIS.map((q) => ord[Math.min(ord.length - 1, Math.floor(q * ord.length))]);
  // num mês, mais de 40% dos hexágonos podem ter nota 0: aí "Muito baixo" fica só com os zeros
  // (sem isso, o 1º corte seria 0 e os zeros cairiam em "Baixo")
  if (cortes[0] <= 0) cortes[0] = 0.0005; // notas têm 3 casas, então qualquer nota positiva é >= 0,001
  // garante cortes estritamente crescentes (exigência do MapLibre)
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
