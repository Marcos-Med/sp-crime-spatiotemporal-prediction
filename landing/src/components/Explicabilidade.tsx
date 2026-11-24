import { useState } from 'react';
import type { AlvoMetricas, ArquivoMetricas, ArquivoVariaveis, GrupoVariavel, Metricas } from '../types/dados';
import { fmt } from '../lib/cores';

const GRUPOS: Record<GrupoVariavel, string> = {
  historico: 'Histórico de crimes',
  vizinhanca: 'Vizinhança',
  calendario: 'Época do ano',
  territorio: 'Domicílios',
  social: 'Perfil da população',
};

const EXPLICA_METRICAS = [
  { id: 'r2', nome: 'R²', melhor: 'maior', texto: 'Quanto da diferença entre lugares e meses o modelo consegue explicar. Vai de 0 a 1; quanto mais perto de 1, melhor.' },
  { id: 'mae', nome: 'MAE', melhor: 'menor', texto: 'Erro médio: em média, quanto a previsão erra para mais ou para menos em cada hexágono.' },
  { id: 'rmse', nome: 'RMSE', melhor: 'menor', texto: 'Parecido com o MAE, mas pune mais os erros grandes. Mostra se o modelo às vezes erra feio.' },
] as const;

const casasMetrica: Record<keyof Metricas, number> = { r2: 3, mae: 4, rmse: 4, pai: 1 };
const data = (d: string) => d.split('-').reverse().join('/');

function Celula({ v, k }: { v: number | null; k: keyof Metricas }) {
  return v === null ? <td className="falta" title="Ainda não calculado">—</td> : <td>{fmt(v, casasMetrica[k])}</td>;
}

function Tabela({ alvo }: { alvo: AlvoMetricas }) {
  return (
    <div className="tabela-rolagem">
      <table className="tabela-metricas">
        <thead>
          <tr><th scope="col">Modelo</th>{EXPLICA_METRICAS.map((m) => <th key={m.id} scope="col">{m.nome}<small>{m.melhor} é melhor</small></th>)}</tr>
        </thead>
        <tbody>
          {alvo.modelos.map((mod) => (
            <tr key={mod.nome} className={mod.principal ? 'principal' : ''}>
              <th scope="row">{mod.nome}{mod.descricao && <small>{mod.descricao}</small>}</th>
              {(['r2', 'mae', 'rmse'] as const).map((k) => <Celula key={k} v={mod.metricas[k]} k={k} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Abas({ itens, ativo, onAtivo, rotulo }: { itens: string[]; ativo: number; onAtivo: (i: number) => void; rotulo: string }) {
  return (
    <div className="segmentado abas" role="tablist" aria-label={rotulo}>
      {itens.map((n, i) => (
        <button key={n} type="button" role="tab" aria-selected={i === ativo} className={i === ativo ? 'ativo' : ''} onClick={() => onAtivo(i)}>{n}</button>
      ))}
    </div>
  );
}

export default function Explicabilidade({ variaveis, metricas }: { variaveis: ArquivoVariaveis; metricas: ArquivoMetricas }) {
  const [alvoVar, setAlvoVar] = useState(0);
  const [alvoMet, setAlvoMet] = useState(0);
  const av = variaveis.alvos[alvoVar];
  const vs = [...av.variaveis].sort((a, b) => b.importancia - a.importancia);
  const historico = Math.round(vs.filter((v) => v.grupo === 'historico').reduce((s, v) => s + v.importancia, 0) * 100);

  return (
    <section className="secao secao-alt" id="explicabilidade">
      <div className="secao-int">
        <p className="sobretitulo">Explicabilidade</p>
        <h2>O que o modelo leva em conta</h2>
        <p className="intro">
          Cada previsão usa informações sobre o hexágono. Abaixo estão as que mais pesam no modelo final de{' '}
          {av.nome.toLowerCase()}{av.modelo ? ` (${av.modelo.replace(/^Random Forest/, 'random forest')})` : ''}:
          a porcentagem é a parte de cada uma no peso total do modelo. O histórico de crimes responde por {historico}% desse
          peso.{av.pesoBairro !== undefined && <> Cada dado do bairro pesa pouco sozinho, mas, somados, os do Censo e do IPVS
          chegam a {fmt(av.pesoBairro * 100)}%.</>}{' '}
          Cada modelo mede importância do seu jeito, então não compare as porcentagens entre tipos de crime. Elas mostram
          o que ajuda a prever, não o que causa o crime.
        </p>

        <Abas itens={variaveis.alvos.map((a) => a.nome)} ativo={alvoVar} onAtivo={setAlvoVar} rotulo="Tipo de crime" />

        <ul className="variaveis">
          {vs.map((v) => (
            <li key={v.id}>
              <div className="var-cab">
                <span className="var-nome">{v.nome}</span>
                <span className="var-peso">{fmt(v.importancia * 100)}%</span>
              </div>
              <div className="var-trilho"><span className={`var-barra grupo-${v.grupo}`} style={{ width: `${Math.max(0.6, v.importancia * 100)}%` }} /></div>
              <p><span className={`grupo-tag grupo-${v.grupo}`}>{GRUPOS[v.grupo]}</span> {v.explicacao}</p>
            </li>
          ))}
          {av.outras && av.outras.quantidade > 0 && (
            <li className="var-outras">
              <div className="var-cab">
                <span className="var-nome">Outras {av.outras.quantidade} variáveis</span>
                <span className="var-peso">{fmt(av.outras.importancia * 100)}%</span>
              </div>
              <div className="var-trilho"><span className="var-barra" style={{ width: `${av.outras.importancia * 100}%` }} /></div>
              <p>
                Cada uma pesa no máximo {fmt(av.outras.maior * 100)}%. A maioria é do perfil do bairro: população, moradores
                por domicílio, jovens, alfabetização, cor da população, tipo de moradia e IPVS.
              </p>
            </li>
          )}
        </ul>

        <h3 className="sub">O modelo é melhor do que o óbvio?</h3>
        <p className="intro">
          Um modelo só vale a pena se acertar mais do que regras simples. No teste final ({data(metricas.periodoTeste.inicio)} a {data(metricas.periodoTeste.fim)}),
          um ano que o modelo nunca viu, ele errou de 2% a 4% menos que a média recente e de 12% a 38% menos que a média
          do hexágono. É um ganho pequeno, mas se repetiu no teste. Os erros estão na escala de {metricas.escala}, não em
          número de crimes.
        </p>
        <p className="intro">
          As métricas usam as 1.260 células do modelo. O mapa mostra 1.208 porque 52 células com coordenada errada caem
          fora da Grande SP.
        </p>
        <Abas itens={metricas.alvos.map((a) => a.nome)} ativo={alvoMet} onAtivo={setAlvoMet} rotulo="Tipo de crime" />
        <Tabela alvo={metricas.alvos[alvoMet]} />

        <dl className="glossario">
          {EXPLICA_METRICAS.map((m) => (
            <div key={m.id}><dt>{m.nome}</dt><dd>{m.texto}</dd></div>
          ))}
        </dl>
      </div>
    </section>
  );
}
