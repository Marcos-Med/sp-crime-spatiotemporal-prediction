// Topo da página, com a arte da Grande São Paulo em hexágonos.
import { useEffect, useMemo, useRef } from 'react';
import { cellToBoundary } from 'h3-js';
import type { Dados } from '../App';
import { CORES_RISCO, calcularCortes, classeDe, fmt } from '../lib/cores';
import { mesCurto, valoresDoFiltro } from '../lib/periodo';

const W = 640, H = 460, MARGEM = 14;

function ArteRegiao({ dados }: { dados: Dados | null }) {
  const tela = useRef<HTMLCanvasElement>(null);

  const desenho = useMemo(() => {
    if (!dados) return null;
    const { hexagonos, meses, alvos } = dados.previsoes;
    const valores = valoresDoFiltro(dados.previsoes, alvos[0].id, { tipo: 'tudo', mes: meses[0], ano: 0 });
    const cortes = calcularCortes(valores);
    const poligonos = dados.contornos.features.flatMap((f) => {
      const g = f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
      return g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    });
    let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
    for (const p of poligonos) for (const [x, y] of p[0]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    const dentro = (anel: number[][]) => anel.every(([x, y]) => x >= x0 && x <= x1 && y >= y0 && y <= y1);
    const todos = hexagonos.map((h) => cellToBoundary(h.h3, true));
    const idx = todos.flatMap((anel, i) => (dentro(anel) ? [i] : []));
    const aneis = idx.map((i) => todos[i]);
    const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
    const escala = Math.min((W - 2 * MARGEM) / ((x1 - x0) * k), (H - 2 * MARGEM) / (y1 - y0));
    const ox = (W - (x1 - x0) * k * escala) / 2, oy = (H - (y1 - y0) * escala) / 2;
    const proj = (x: number, y: number): [number, number] => [ox + (x - x0) * k * escala, oy + (y1 - y) * escala];
    let topo = idx.findIndex((i) => !hexagonos[i].imputado);
    if (topo < 0) topo = 0;
    idx.forEach((i, k) => { if (!hexagonos[i].imputado && valores[i] > valores[idx[topo]]) topo = k; });
    const centro = aneis[topo].slice(0, 6).reduce(([a, b], [x, y]) => [a + x / 6, b + y / 6], [0, 0]);
    const iTopo = idx[topo];
    const nome = dados.municipios.find((m) => m.codigo === hexagonos[iTopo].municipio)?.nome ?? '';
    return {
      aneis: aneis.map((anel) => anel.map(([x, y]) => proj(x, y))),
      classes: idx.map((i) => classeDe(valores[i], cortes)),
      contornos: poligonos.map((p) => p[0].map(([x, y]) => proj(x, y))),
      destaque: { pos: proj(centro[0], centro[1]), valor: valores[iTopo], nome, periodo: `${mesCurto(meses[0])} a ${mesCurto(meses[meses.length - 1])}` },
    };
  }, [dados]);

  useEffect(() => {
    const c = tela.current;
    if (!c || !desenho) return;
    const pintar = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      c.width = W * dpr; c.height = H * dpr;
      const ctx = c.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const css = getComputedStyle(document.documentElement);
      desenho.aneis.forEach((anel, i) => {
        const cl = desenho.classes[i];
        ctx.globalAlpha = 0.45 + cl * 0.13;
        ctx.fillStyle = CORES_RISCO[cl];
        ctx.beginPath();
        anel.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.fill();
      });
      ctx.globalAlpha = 1;
      ctx.strokeStyle = css.getPropertyValue('--bg').trim() || '#fff';
      ctx.lineWidth = 0.9;
      for (const p of desenho.contornos) {
        ctx.beginPath();
        p.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        ctx.stroke();
      }
    };
    pintar();
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', pintar);
    return () => mq.removeEventListener('change', pintar);
  }, [desenho]);

  const d = desenho?.destaque;
  return (
    <div className="arte-regiao">
      <canvas ref={tela} role="img" aria-label="Mapa da Grande São Paulo dividido em hexágonos coloridos pelo risco previsto" />
      {d && (
        <>
          <span className="arte-alvo" style={{ left: `${(d.pos[0] / W) * 100}%`, top: `${(d.pos[1] / H) * 100}%` }} aria-hidden="true" />
          <div className={`arte-cartao${d.pos[0] > W * 0.55 ? ' arte-cartao-esq' : ''}`} style={{ left: `${(d.pos[0] / W) * 100}%`, top: `${(d.pos[1] / H) * 100}%` }}>
            <span className="arte-cartao-rotulo">{dados?.previsoes.fonte === 'mock' ? 'Exemplo ilustrativo' : 'Previsão do modelo'}</span>
            <strong>Nota de risco {fmt(d.valor, 2)}</strong>
            <span>a mais alta, em {d.nome}</span>
            <span>média de {d.periodo}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default function Hero({ dados }: { dados: Dados | null }) {
  const nHex = dados?.previsoes.hexagonos.length;
  return (
    <section className="hero" id="inicio">
      <div className="hero-int">
        <div className="hero-texto">
          <p className="sobretitulo">Projeto RP2 · Grande São Paulo</p>
          <h1>Onde <span className="letra-f">f</span>urtos e roubos tendem a acontecer</h1>
          <p className="lead">
            Dividimos a Região Metropolitana de São Paulo em hexágonos de cerca de 5 km² e usamos 2,6 milhões de
            furtos e roubos registrados pela SSP-SP para estimar o risco de cada hexágono no mês seguinte.
            O resultado é um mapa que ajuda a planejar onde prevenir.
          </p>
          <div className="hero-acoes">
            <a className="botao" href="#mapa">Explorar o mapa</a>
            <a className="botao botao-sec" href="#resultados">Ver os resultados</a>
          </div>
        </div>
        <figure className="hero-arte">
          <ArteRegiao dados={dados} />
          <figcaption>
            {nHex ? nHex.toLocaleString('pt-BR') : '…'} hexágonos na Grande São Paulo.{' '}
            {dados?.previsoes.fonte === 'mock'
              ? 'Cores ilustrativas: as previsões reais por hexágono ainda não foram exportadas.'
              : 'Cores: nota média de risco de furtos e roubos prevista pelo modelo nos 12 meses do teste. O destaque ignora os hexágonos que receberam as ocorrências sem endereço exato.'}
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
