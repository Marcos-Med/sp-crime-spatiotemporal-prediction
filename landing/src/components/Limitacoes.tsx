// Seção de limitações e próximos passos.
const LIMITES = [
  {
    titulo: 'Ganho pequeno sobre uma regra simples',
    texto: 'O modelo errou só 2% a 4% menos que a média dos últimos meses, e nos 5% de hexágonos mais arriscados os dois apontam praticamente os mesmos lugares. A maior parte do acerto vem de o crime se repetir nos mesmos lugares.',
  },
  {
    titulo: '11% das ocorrências sem endereço exato',
    texto: 'Cerca de 293 mil dos 2,59 milhões de furtos e roubos vieram sem coordenada e foram colocados num único ponto de cada cidade (a mediana das coordenadas dela). O hexágono desse ponto fica com a nota inflada: na capital, ele é o mais "quente" do mapa. Fora da capital, 8 das 9 células que ficam sempre no topo de crime total são desse tipo. Ao passar o mouse, o mapa avisa quando é o caso.',
  },
  {
    titulo: 'Só enxerga o que é registrado',
    texto: 'O modelo aprende com boletins de ocorrência. Crimes que não são denunciados não aparecem, e lugares onde se denuncia mais podem parecer mais perigosos.',
  },
  {
    titulo: 'Variáveis sociais pedem cuidado',
    texto: 'O modelo usa o perfil do bairro, como idade, alfabetização e cor da população, pelo Censo. Cada uma pesa pouco sozinha, mas, somadas, ficam com 13% a 25% do peso do modelo. São de 2022 e não mudam mês a mês. Ajudam a diferenciar lugares, não explicam o crime e podem reforçar estigmas. Um hexágono vermelho fala do lugar, nunca de quem mora ali.',
  },
  {
    titulo: 'Uma nota por mês, não uma contagem',
    texto: 'O modelo prevê uma nota de risco por mês em hexágonos de cerca de 5 km², então o mapa não mostra dias nem semanas. A nota serve para comparar lugares e meses: não é o número de crimes nem uma probabilidade. Hexágonos sem nenhum crime registrado ficam fora do modelo.',
  },
  {
    titulo: 'Só um mês à frente',
    texto: 'A previsão usa o que aconteceu até o mês anterior. Não testamos prever vários meses de uma vez, e o ganho precisa ser conferido de novo quando houver dados mais recentes.',
  },
];

const PROXIMOS = [
  'Validar as coordenadas contra o contorno dos municípios antes de agregar.',
  'Testar previsões para horizontes mais longos.',
  'Incluir variáveis que mudem mês a mês.',
  'Escolher o modelo também pela captura de pontos quentes.',
  'Avaliar o mapa com potenciais usuários.',
];

export default function Limitacoes() {
  return (
    <section className="secao" id="limitacoes">
      <div className="secao-int">
        <p className="sobretitulo">Limitações e cuidados</p>
        <h2>O que este mapa não diz</h2>
        <p className="intro">Toda previsão tem limites. Conhecer esses limites é o que permite usar o mapa com responsabilidade.</p>
        <ul className="limites">
          {LIMITES.map((l) => (
            <li key={l.titulo}>
              <h3>{l.titulo}</h3>
              <p>{l.texto}</p>
            </li>
          ))}
        </ul>
        <h3 className="sub">Próximos passos</h3>
        <ul className="proximos">
          {PROXIMOS.map((p) => <li key={p}>{p}</li>)}
        </ul>
      </div>
    </section>
  );
}
