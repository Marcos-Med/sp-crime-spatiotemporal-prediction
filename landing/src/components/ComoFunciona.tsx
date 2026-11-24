const PASSOS = [
  {
    titulo: 'Dividimos o mapa em hexágonos',
    texto: 'Cada hexágono H3 cobre cerca de 5 km², o tamanho de um bairro pequeno. Assim comparamos lugares do mesmo tamanho, sem depender de limites de bairro.',
  },
  {
    titulo: 'Juntamos o que se sabe de cada lugar',
    texto: 'Quantos furtos e roubos aconteceram ali nos últimos meses, o que acontece nos hexágonos vizinhos e o perfil do bairro pelo Censo 2022 e pelo índice de vulnerabilidade social (IPVS).',
  },
  {
    titulo: 'O modelo aprende com o passado',
    texto: 'Os modelos estudam os registros de 2023 a meados de 2025 e aprendem a corrigir o erro da média recente de cada lugar. O teste final é em um ano que eles nunca viram: jul/2025 a jun/2026.',
  },
  {
    titulo: 'Geramos o mapa de risco',
    texto: 'Para cada mês, cada hexágono recebe uma nota de risco de 0 a 1. As cores mostram onde o risco é maior em comparação com o resto da região.',
  },
];

export default function ComoFunciona() {
  return (
    <section className="secao" id="projeto">
      <div className="secao-int">
        <p className="sobretitulo">O projeto</p>
        <h2>Prever para prevenir</h2>
        <p className="intro">
          Polícia, prefeituras e pesquisadores precisam decidir onde concentrar esforços. Este projeto usa dados públicos
          de ocorrências para indicar, com antecedência, as áreas onde o risco registrado tende a ser maior. Ele não aponta
          pessoas, só lugares e períodos.
        </p>
        <dl className="dados-reais" aria-label="Números da base de dados">
          <div><dt>2,59 mi</dt><dd>furtos e roubos na Grande SP, de 2022 a jun/2026, tirados de 5,35 mi boletins da SSP-SP</dd></div>
          <div><dt>70%</dt><dd>dos furtos e roubos se concentram em 10% dos hexágonos do modelo (126 de 1.260)</dd></div>
          <div><dt>11%</dt><dd>desses furtos e roubos não têm localização exata</dd></div>
        </dl>
        <ol className="passos">
          {PASSOS.map((p, i) => (
            <li key={p.titulo}>
              <span className="passo-num" aria-hidden="true">{i + 1}</span>
              <h3>{p.titulo}</h3>
              <p>{p.texto}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
