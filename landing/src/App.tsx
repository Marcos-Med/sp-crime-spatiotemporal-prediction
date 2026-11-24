import { useEffect, useState } from 'react';
import type { ArquivoMetricas, ArquivoPrevisoes, ArquivoVariaveis, MetadadosMunicipio } from './types/dados';
import { buscarContornosMunicipios, buscarMetricas, buscarMunicipios, buscarPrevisoes, buscarVariaveis } from './services/api';
import Cabecalho from './components/Cabecalho';
import Hero from './components/Hero';
import ComoFunciona from './components/ComoFunciona';
import MapaRisco from './components/mapa/MapaRisco';
import Explicabilidade from './components/Explicabilidade';
import Resultados from './components/Resultados';
import Limitacoes from './components/Limitacoes';
import Rodape from './components/Rodape';

export interface Dados {
  previsoes: ArquivoPrevisoes;
  municipios: MetadadosMunicipio[];
  contornos: GeoJSON.FeatureCollection;
  variaveis: ArquivoVariaveis;
  metricas: ArquivoMetricas;
}

export default function App() {
  const [dados, setDados] = useState<Dados | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([buscarPrevisoes(), buscarMunicipios(), buscarContornosMunicipios(), buscarVariaveis(), buscarMetricas()])
      .then(([previsoes, municipios, contornos, variaveis, metricas]) =>
        setDados({ previsoes, municipios, contornos, variaveis, metricas }),
      )
      .catch((e) => setErro(String(e)));
  }, []);

  return (
    <>
      <Cabecalho mock={dados?.previsoes.fonte !== 'modelo'} />
      <main>
        <Hero dados={dados} />
        <ComoFunciona />
        {erro && <p className="erro">Não foi possível carregar os dados: {erro}</p>}
        {dados ? <MapaRisco dados={dados} /> : <section className="secao carregando">Carregando o mapa…</section>}
        {dados && <Resultados metricas={dados.metricas} />}
        {dados && <Explicabilidade variaveis={dados.variaveis} metricas={dados.metricas} />}
        <Limitacoes />
      </main>
      <Rodape />
    </>
  );
}
