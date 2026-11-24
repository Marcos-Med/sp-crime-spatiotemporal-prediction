// Configurações do mapa: fundo, transparência, centro e zoom.
export const ESTILO_MAPA_BASE: string | null = 'https://tiles.openfreemap.org/styles/positron';

export const OPACIDADE_HEX_POR_ZOOM: [number, number][] = [
  [8, 0.85],
  [11, 0.6],
  [13, 0.4],
];

export const CENTRO_INICIAL: [number, number] = [-46.55, -23.6];
export const ZOOM_INICIAL = 8.6;
