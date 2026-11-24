import type { MetadadosMunicipio } from '../../types/dados';
import { CORES_RISCO, NOMES_RISCO, fmt } from '../../lib/cores';

export interface ResumoMunicipio {
  media: number; // nota média de risco dos hexágonos do município
  porClasse: number[];
  maiorHex: { h3: string; valor: number } | null;
}

interface Props {
  meta: MetadadosMunicipio;
  resumo: ResumoMunicipio;
  periodo: string;
  alvo: string;
  onFechar: () => void;
}

const num = (v: number | null, casas = 0, sufixo = '') => (v === null ? '—' : `${fmt(v, casas)}${sufixo}`);

export default function PainelMunicipio({ meta, resumo, periodo, alvo, onFechar }: Props) {
  const nHex = resumo.porClasse.reduce((a, b) => a + b, 0) || 1;
  const altos = resumo.porClasse[3] + resumo.porClasse[4];
  const carregado = meta.hexagonos !== null;
  return (
    <aside className="painel" aria-label={`Dados de ${meta.nome}`}>
      <div className="painel-topo">
        <div>
          <p className="sobretitulo">Município · IBGE {meta.codigo}</p>
          <h3>{meta.nome}</h3>
        </div>
        <button type="button" className="fechar" onClick={onFechar} aria-label="Fechar painel">×</button>
      </div>

      <div className="painel-destaque">
        <span className="num">{fmt(resumo.media, 2)}</span>
        <span>nota média de risco ({alvo.toLowerCase()}), {periodo}</span>
      </div>

      <div className="barra-classes" aria-label="Hexágonos por nível de risco">
        {resumo.porClasse.map((n, i) => n > 0 && (
          <span key={i} style={{ flexGrow: n, background: CORES_RISCO[i] }} title={`${NOMES_RISCO[i]}: ${n} hexágonos`} />
        ))}
      </div>
      <p className="painel-nota">
        {altos} de {nHex} hexágonos ({fmt((altos / nHex) * 100)}%) estão em risco alto ou muito alto.
        {resumo.maiorHex && <> O mais crítico tem nota {fmt(resumo.maiorHex.valor, 2)}.</>}
      </p>

      <h4>Sobre o lugar</h4>
      {carregado ? (
        <>
          <dl className="lista-dados">
            <div><dt>Furtos e roubos nos hexágonos</dt><dd>{meta.crimes ? fmt(meta.crimes.total) : '—'}</dd></div>
            <div><dt>Furtos / roubos</dt><dd>{meta.crimes ? `${fmt(meta.crimes.furto)} / ${fmt(meta.crimes.roubo)}` : '—'}</dd></div>
            <div><dt>Hexágonos no mapa</dt><dd>{num(meta.hexagonos)}</dd></div>
            <div><dt>Área coberta</dt><dd>{num(meta.areaKm2, 0, ' km²')}</dd></div>
            <div><dt>IPVS médio (1 a 6)</dt><dd>{num(meta.ipvsMedio, 1)}</dd></div>
            <div><dt>Alfabetização (15+)</dt><dd>{num(meta.taxaAlfabetizacao, 1, '%')}</dd></div>
            <div><dt>Jovens de 15 a 29 anos</dt><dd>{num(meta.pctJovens15a29, 1, '%')}</dd></div>
          </dl>
          <p className="painel-nota">
            Ocorrências de jan/2022 a jun/2026 nos hexágonos do município: cada hexágono conta para a cidade com mais
            ocorrências nele, então o total pode diferir um pouco da contagem pela cidade do boletim. IPVS é o grupo de vulnerabilidade social, de 1 (baixíssima) a 6 (muito
            alta); setores sem classificação receberam a mediana do município. IPVS, alfabetização e jovens são médias
            nos hexágonos do município (Censo 2022 e IPVS 2022).
          </p>
        </>
      ) : (
        <p className="painel-nota">
          Os dados do município (ocorrências registradas, IPVS, alfabetização e jovens) vêm da base do Marcos e ainda não
          foram carregados.
        </p>
      )}
    </aside>
  );
}
