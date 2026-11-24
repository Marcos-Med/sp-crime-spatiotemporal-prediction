// Seção com os resultados e as respostas do artigo.
import type { ArquivoMetricas } from '../types/dados';
import { fmt } from '../lib/cores';

const RESPOSTAS = [
  {
    pergunta: 'Os modelos superam regras simples?',
    texto: 'Sim, mas por pouco: erram de 2% a 4% menos que a média recente (EWM3), a referência mais difícil, e de 12% a 38% menos que a média do hexágono. O ganho se repetiu no teste. Os melhores modelos aprendem a corrigir o erro da média recente.',
  },
  {
    pergunta: 'Vale separar lugares de muito e pouco crime?',
    texto: 'Não trouxe ganho consistente. Testamos um modelo por grupo e um híbrido para a baixa atividade, mas um modelo único para toda a região foi o escolhido nos três tipos de crime.',
  },
  {
    pergunta: 'O que mais pesa na previsão?',
    texto: 'O histórico do próprio lugar. Em crime total e furto, o mesmo mês do ano anterior e os erros recentes; em roubo, a média recente e a média de 12 meses. Os dados do Censo e do IPVS somam de 13% a 25%, e nenhum passa de 4,3% sozinho.',
  },
  {
    pergunta: 'O que os mapas mostram?',
    texto: 'O risco se concentra no centro expandido da capital e se estende pelo entorno: 50 das 61 células de maior nota média ficam na capital. Em crime total, 54 células ficam entre as 5% de maior nota nos 12 meses, e 98,5% do topo de cada mês, em média, é igual ao da média recente. Parte dos pontos quentes fora da capital vem dos registros sem coordenada, e não de um lugar comprovadamente mais perigoso.',
  },
];

export default function Resultados({ metricas }: { metricas: ArquivoMetricas }) {
  return (
    <section className="secao" id="resultados">
      <div className="secao-int">
        <p className="sobretitulo">Resultados</p>
        <h2>O que descobrimos</h2>
        <p className="intro">
          Comparamos cinco algoritmos (Ridge, Ridge log, GAM, EBM e Random Forest) com duas regras simples. O de menor
          erro médio (RMSE) na validação, em três períodos de 2024 a meados de 2025, foi testado uma única vez, de jul/2025 a jun/2026.
        </p>

        <div className="tabela-rolagem">
          <table className="tabela-metricas">
            <thead>
              <tr>
                <th scope="col">Tipo de crime</th>
                <th scope="col">R²<small>no teste</small></th>
                <th scope="col">Ganho sobre a média recente<small>EWM3, no teste</small></th>
                <th scope="col">Ganho sobre a média do hexágono<small>fixa, no teste</small></th>
                <th scope="col">Ganho sobre a média recente<small>EWM3, na validação</small></th>
              </tr>
            </thead>
            <tbody>
              {metricas.alvos.map((a) => {
                const final = a.modelos.find((m) => m.principal);
                const r2 = final?.metricas.r2 ?? null;
                return (
                  <tr key={a.id}>
                    <th scope="row">{a.nome}<small>{final?.nome}</small></th>
                    <td>{r2 === null ? '—' : fmt(r2, 3)}</td>
                    <td>{a.ganhos ? `${fmt(a.ganhos.testeEwm3, 2)}%` : '—'}</td>
                    <td>{a.ganhos ? `${fmt(a.ganhos.testeMediaFixa, 2)}%` : '—'}</td>
                    <td>{a.ganhos ? `${fmt(a.ganhos.validacaoEwm3, 2)}%` : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="aviso-precisao">
          Ganho é quanto o RMSE ficou menor. Cada tipo de crime tem a própria escala, então compare os ganhos, e não os erros, entre eles.
        </p>

        <ul className="limites respostas">
          {RESPOSTAS.map((r) => (
            <li key={r.pergunta}>
              <h3>{r.pergunta}</h3>
              <p>{r.texto}</p>
            </li>
          ))}
        </ul>

        <p className="conclusao">
          <strong>Na prática:</strong> uma regra simples como a média recente já aponta quase os mesmos lugares críticos.
          A priorização pode se apoiar em regras transparentes, com o modelo como refinamento.
        </p>
      </div>
    </section>
  );
}
