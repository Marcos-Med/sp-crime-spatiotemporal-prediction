// Mapa de calor: desenha os hexágonos H3 e colore pela nota de risco.
import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { type GeoJSONSource, type Map as MapaML, type StyleSpecification } from 'maplibre-gl';
import { cellToBoundary } from 'h3-js';
import type { Dados } from '../../App';
import Filtros from './Filtros';
import PainelMunicipio, { type ResumoMunicipio } from './PainelMunicipio';
import { SOBRE_A_NOTA, descreverFiltro, valoresDoFiltro, type FiltroTempo } from '../../lib/periodo';
import { CORES_RISCO, NOMES_RISCO, calcularCortes, classeDe, fmt } from '../../lib/cores';
import { CENTRO_INICIAL, ESTILO_MAPA_BASE, OPACIDADE_HEX_POR_ZOOM, ZOOM_INICIAL } from '../../lib/config';

const ESTILO_VAZIO: StyleSpecification = { version: 8, sources: {}, layers: [] };
const USAR_MAPA_BASE = !!ESTILO_MAPA_BASE;

function limitesDe(geom: GeoJSON.Geometry): [[number, number], [number, number]] {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  const visita = (c: unknown): void => {
    if (typeof (c as number[])[0] === 'number') {
      const [x, y] = c as number[];
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    } else (c as unknown[]).forEach(visita);
  };
  visita((geom as GeoJSON.Polygon).coordinates);
  return [[x0, y0], [x1, y1]];
}

export default function MapaRisco({ dados }: { dados: Dados }) {
  const { previsoes, municipios, contornos } = dados;
  const caixa = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaML | null>(null);
  const [pronto, setPronto] = useState(false);
  const [filtro, setFiltro] = useState<FiltroTempo>({ tipo: 'mes', mes: '2025-12', ano: 2025 });
  const [alvo, setAlvo] = useState(previsoes.alvos[0].id);
  const [municipio, setMunicipio] = useState('');
  const [painel, setPainel] = useState(false);
  const dicaRef = useRef<HTMLDivElement>(null);
  const alvoRef = useRef('');

  const estado = useRef({ municipio, painel });
  estado.current = { municipio, painel };

  const nomePorCodigo = useMemo(() => Object.fromEntries(municipios.map((m) => [m.codigo, m.nome])), [municipios]);
  const valores = useMemo(() => valoresDoFiltro(previsoes, alvo, filtro), [previsoes, alvo, filtro]);
  const cortes = useMemo(() => calcularCortes(valores), [valores]);
  const nomeAlvo = previsoes.alvos.find((a) => a.id === alvo)?.nome ?? alvo;
  alvoRef.current = nomeAlvo;
  const periodo = descreverFiltro(filtro, previsoes.meses);

  const hexGeo = useMemo<GeoJSON.FeatureCollection<GeoJSON.Polygon>>(() => ({
    type: 'FeatureCollection',
    features: previsoes.hexagonos.map((h, i) => {
      const anel = cellToBoundary(h.h3, true);
      return { type: 'Feature', id: i, properties: { h3: h.h3, m: h.municipio, v: 0, imp: h.imputado ? 1 : 0 }, geometry: { type: 'Polygon', coordinates: [anel] } };
    }),
  }), [previsoes]);

  const selecionar = (codigo: string, abrirPainel = false) => {
    setMunicipio(codigo);
    setPainel(abrirPainel);
    const m = mapa.current;
    if (!m) return;
    if (!codigo) {
      m.flyTo({ center: CENTRO_INICIAL, zoom: ZOOM_INICIAL, duration: 900 });
      return;
    }
    const f = contornos.features.find((f) => f.properties?.codigo === codigo);
    if (f) m.fitBounds(limitesDe(f.geometry), { padding: 40, duration: 900, maxZoom: 12.5 });
  };
  const selecionarRef = useRef(selecionar);
  selecionarRef.current = selecionar;

  useEffect(() => {
    if (!caixa.current) return;
    const m = new maplibregl.Map({
      container: caixa.current,
      style: ESTILO_MAPA_BASE ?? ESTILO_VAZIO,
      center: CENTRO_INICIAL,
      zoom: ZOOM_INICIAL,
      minZoom: 7.5,
      maxZoom: 14,
      attributionControl: USAR_MAPA_BASE ? { compact: true } : false,
      cooperativeGestures: true,
      locale: {
        'CooperativeGesturesHandler.WindowsHelpText': 'Use Ctrl + rolagem para dar zoom no mapa',
        'CooperativeGesturesHandler.MacHelpText': 'Use ⌘ + rolagem para dar zoom no mapa',
        'CooperativeGesturesHandler.MobileHelpText': 'Use dois dedos para mover o mapa',
        'NavigationControl.ZoomIn': 'Aproximar',
        'NavigationControl.ZoomOut': 'Afastar',
        'NavigationControl.ResetBearing': 'Voltar para o norte',
      },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    mapa.current = m;

    let carregou = false;
    const usarSemFundo = () => { if (!carregou) { carregou = true; m.setStyle(ESTILO_VAZIO); } };
    const tempo = USAR_MAPA_BASE ? window.setTimeout(usarSemFundo, 8000) : 0;
    m.on('error', (e) => { if (!m.loaded() && !carregou && /style|fetch|Failed/i.test(String(e.error?.message))) usarSemFundo(); });

    m.on('load', () => {
      carregou = true;
      window.clearTimeout(tempo);
      m.addSource('municipios', { type: 'geojson', data: contornos, promoteId: 'codigo' });
      m.addSource('hex', { type: 'geojson', data: hexGeo });
      const antesDe = m.getStyle().layers.find((l) => l.type === 'symbol')?.id;
      m.addLayer({ id: 'mun-fundo', type: 'fill', source: 'municipios', paint: { 'fill-color': '#8a93a8', 'fill-opacity': USAR_MAPA_BASE ? 0.02 : 0.12 } }, antesDe);
      m.addLayer({ id: 'hex', type: 'fill', source: 'hex', paint: { 'fill-color': CORES_RISCO[0], 'fill-opacity': 0.85 } }, antesDe);
      m.addLayer({ id: 'hex-hover', type: 'line', source: 'hex', paint: { 'line-color': '#1b2236', 'line-width': 2, 'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 1, 0] } }, antesDe);
      m.addLayer({ id: 'mun-borda', type: 'line', source: 'municipios', paint: { 'line-color': '#4a5470', 'line-width': 0.8, 'line-opacity': 0.7 } }, antesDe);
      m.addLayer({ id: 'mun-sel', type: 'line', source: 'municipios', paint: { 'line-color': '#1b2236', 'line-width': 3 }, filter: ['==', ['get', 'codigo'], ''] }, antesDe);

      m.on('click', 'mun-fundo', (e) => {
        const codigo = e.features?.[0]?.properties?.codigo as string | undefined;
        if (!codigo) return;
        if (estado.current.municipio === codigo) selecionarRef.current(codigo, true);
        else selecionarRef.current(codigo, false);
      });
      let hoverId: number | null = null;
      let quadro = 0;
      let ultimo: { x: number; y: number; f: maplibregl.MapGeoJSONFeature } | null = null;
      const desenhar = () => {
        quadro = 0;
        const d = dicaRef.current;
        if (!d || !ultimo) return;
        const { x, y, f } = ultimo;
        const id = f.id as number;
        if (id !== hoverId) {
          if (hoverId !== null) m.setFeatureState({ source: 'hex', id: hoverId }, { hover: false });
          m.setFeatureState({ source: 'hex', id }, { hover: true });
          hoverId = id;
        }
        d.innerHTML = `Nota de risco <strong>${fmt(Number(f.properties.v), 2)}</strong><span>${alvoRef.current} · ${nomePorCodigo[f.properties.m] ?? ''}</span>` +
          (Number(f.properties.imp) ? '<span>Inclui as ocorrências da cidade sem endereço exato: nota inflada.</span>' : '');
        d.style.transform = `translate(${x + 14}px, ${y - 12}px) translateY(-100%)`;
        d.hidden = false;
      };
      m.on('mousemove', 'hex', (e) => {
        const f = e.features?.[0];
        if (!f) return;
        ultimo = { x: e.point.x, y: e.point.y, f };
        if (!quadro) quadro = requestAnimationFrame(desenhar);
      });
      m.on('mouseenter', 'hex', () => { m.getCanvas().style.cursor = 'pointer'; });
      m.on('mouseleave', 'hex', () => {
        m.getCanvas().style.cursor = '';
        if (quadro) cancelAnimationFrame(quadro);
        quadro = 0;
        ultimo = null;
        if (hoverId !== null) m.setFeatureState({ source: 'hex', id: hoverId }, { hover: false });
        hoverId = null;
        if (dicaRef.current) dicaRef.current.hidden = true;
      });
      setPronto(true);
    });
    return () => { window.clearTimeout(tempo); m.remove(); mapa.current = null; setPronto(false); };
  }, [contornos, hexGeo, nomePorCodigo]);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !pronto) return;
    hexGeo.features.forEach((f, i) => { f.properties!.v = Math.round(valores[i] * 1000) / 1000; });
    (m.getSource('hex') as GeoJSONSource).setData(hexGeo);
    m.setPaintProperty('hex', 'fill-color', [
      'step', ['get', 'v'], CORES_RISCO[0],
      cortes[0], CORES_RISCO[1], cortes[1], CORES_RISCO[2], cortes[2], CORES_RISCO[3], cortes[3], CORES_RISCO[4],
    ]);
  }, [pronto, valores, cortes, hexGeo]);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !pronto) return;
    m.setFilter('mun-sel', ['==', ['get', 'codigo'], municipio]);
    const aplicarCorLinha = () => {
      const tinta = getComputedStyle(document.documentElement).getPropertyValue('--tinta').trim() || '#161c2e';
      m.setPaintProperty('mun-sel', 'line-color', tinta);
      m.setPaintProperty('hex-hover', 'line-color', tinta);
    };
    aplicarCorLinha();
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', aplicarCorLinha);
    const obs = new MutationObserver(aplicarCorLinha);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    const dentro = ['==', ['get', 'm'], municipio];
    const passos = OPACIDADE_HEX_POR_ZOOM.flatMap(([z, o]) => [z, municipio ? ['case', dentro, o, o * 0.2] : o]);
    m.setPaintProperty('hex', 'fill-opacity', ['interpolate', ['linear'], ['zoom'], ...passos] as never);
    return () => { mq.removeEventListener('change', aplicarCorLinha); obs.disconnect(); };
  }, [pronto, municipio]);

  const resumo = useMemo(() => {
    const porMun: Record<string, ResumoMunicipio> = {};
    let soma = 0, muitoAlto = 0;
    previsoes.hexagonos.forEach((h, i) => {
      const v = valores[i];
      const c = classeDe(v, cortes);
      soma += v;
      if (c === 4) muitoAlto++;
      const r = (porMun[h.municipio] ??= { media: 0, porClasse: [0, 0, 0, 0, 0], maiorHex: null });
      r.media += v;
      r.porClasse[c]++;
      if (!r.maiorHex || v > r.maiorHex.valor) r.maiorHex = { h3: h.h3, valor: v };
    });
    for (const r of Object.values(porMun)) r.media /= r.porClasse.reduce((a, b) => a + b, 0) || 1;
    const media = soma / (previsoes.hexagonos.length || 1);
    const lider = Object.entries(porMun).sort((a, b) => b[1].media - a[1].media)[0];
    return { media, muitoAlto, porMun, lider };
  }, [previsoes, valores, cortes]);

  const metaSel = municipios.find((m) => m.codigo === municipio);
  const resumoSel = municipio ? resumo.porMun[municipio] : null;
  const limitesLegenda = [0, ...cortes];
  const casasLegenda = cortes[3] < 0.1 ? 3 : 2;
  const fmtCorte = (v: number) => (v <= 0 ? '0' : fmt(v, v < 0.01 ? 3 : casasLegenda));

  return (
    <section className="secao secao-mapa" id="mapa">
      <div className="secao-int">
        <p className="sobretitulo">Mapa de risco preditivo</p>
        <h2>Explore a previsão por região</h2>
        <p className="intro">
          Cada mês mostra a nota que o modelo previu para jul/2025 a jun/2026, usando só o que tinha acontecido até o mês
          anterior. Passe o mouse sobre um hexágono para ver a nota; clique num município para aproximar e de novo para ver os dados dele.
        </p>

        {previsoes.fonte === 'mock' && (
          <p className="aviso-mapa">
            <strong>Mapa ilustrativo.</strong> Os números ainda são simulados: as previsões reais por hexágono ainda não foram exportadas pelo modelo.
          </p>
        )}

        <Filtros filtro={filtro} onFiltro={setFiltro} meses={previsoes.meses} alvos={previsoes.alvos} alvo={alvo} onAlvo={setAlvo}
          municipios={municipios} municipio={municipio} onMunicipio={(c) => selecionar(c)} />

        <div className="faixa-resumo" aria-live="polite">
          <div><span className="num">{municipio && !resumoSel ? '—' : fmt(resumoSel ? resumoSel.media : resumo.media, 2)}</span>
            <span>
              {municipio && !resumoSel
                ? `${nomePorCodigo[municipio]} não tem hexágonos no modelo (nenhum furto ou roubo com localização na base)`
                : `nota média de risco (${nomeAlvo.toLowerCase()}) em ${municipio ? nomePorCodigo[municipio] : 'toda a região'}, ${periodo}`}
            </span></div>
          <div><span className="num">{municipio && !resumoSel ? '—' : fmt(resumoSel ? resumoSel.porClasse[4] : resumo.muitoAlto)}</span>
            <span>hexágonos em risco muito alto</span></div>
          {!municipio && resumo.lider && (
            <div><span className="num num-texto">{nomePorCodigo[resumo.lider[0]]}</span><span>município com a maior nota média</span></div>
          )}
          {municipio && (
            <div className="faixa-acoes">
              {!painel && resumoSel && <button type="button" className="botao botao-peq" onClick={() => setPainel(true)}>Ver dados do município</button>}
              <button type="button" className="botao botao-peq botao-sec" onClick={() => selecionar('')}>Ver toda a região</button>
            </div>
          )}
        </div>

        <div className={`mapa-layout ${painel && metaSel ? 'com-painel' : ''}`}>
          <div className="mapa-moldura">
            <div ref={caixa} className="mapa" role="region" aria-label="Mapa de risco da Grande São Paulo" />
            <div ref={dicaRef} className="dica" hidden />
            <div className="legenda">
              <span className="legenda-titulo">Nota de risco (0 a 1)</span>
              <ul>
                {CORES_RISCO.map((c, i) => (
                  <li key={c}>
                    <span className="amostra" style={{ background: c }} />
                    <span className="legenda-nome">{NOMES_RISCO[i]}</span>
                    <span className="legenda-faixa">
                      {i === 0 && cortes[0] < 0.001 ? '0'
                        : i < 4 ? `${fmtCorte(limitesLegenda[i])}–${fmtCorte(cortes[i])}` : `${fmtCorte(cortes[3])}+`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {painel && metaSel && resumoSel && (
            <PainelMunicipio meta={metaSel} resumo={resumoSel} periodo={periodo} alvo={nomeAlvo} onFechar={() => setPainel(false)} />
          )}
        </div>
        <p className="aviso-precisao"><strong>Sobre a nota:</strong> {SOBRE_A_NOTA}</p>
      </div>
    </section>
  );
}
