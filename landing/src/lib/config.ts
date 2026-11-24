// Configurações fáceis de mudar.

// Mapa de fundo com ruas e nomes: OpenFreeMap (gratuito, sem chave, dados do OpenStreetMap).
// As ruas ficam por baixo dos hexágonos e os nomes por cima.
// Outros estilos gratuitos: 'https://tiles.openfreemap.org/styles/bright' ou '.../liberty'.
// Coloque null para tirar o mapa de fundo (só contornos dos municípios).
export const ESTILO_MAPA_BASE: string | null = 'https://tiles.openfreemap.org/styles/positron';

// Transparência dos hexágonos conforme o zoom: [zoom, opacidade] (0 = invisível, 1 = opaco).
// Afastado: cores fortes para comparar regiões. Aproximado: transparente para ver ruas e nomes.
export const OPACIDADE_HEX_POR_ZOOM: [number, number][] = [
  [8, 0.85],
  [11, 0.6],
  [13, 0.4],
];

// Centro e zoom iniciais (Região Metropolitana de São Paulo)
export const CENTRO_INICIAL: [number, number] = [-46.55, -23.6];
export const ZOOM_INICIAL = 8.6;
