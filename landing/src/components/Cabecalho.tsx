export default function Cabecalho({ mock }: { mock: boolean }) {
  return (
    <header className="cabecalho">
      <div className="cabecalho-int">
        <a href="#inicio" className="marca">
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d="M12 2 20.66 7v10L12 22 3.34 17V7z" fill="var(--risco-4)" />
            <path d="M12 7.5 16.33 10v5L12 17.5 7.67 15v-5z" fill="var(--risco-2)" />
          </svg>
          <span>Mapa de Risco SP</span>
        </a>
        <nav aria-label="Seções">
          <a href="#projeto">O projeto</a>
          <a href="#mapa">Mapa</a>
          <a href="#resultados">Resultados</a>
          <a href="#explicabilidade">Como o modelo decide</a>
          <a href="#limitacoes">Limitações</a>
        </nav>
        {mock && <span className="selo-mock" title="Métricas e variáveis são reais (validação). O mapa ainda usa previsões ilustrativas.">Mapa ilustrativo</span>}
      </div>
    </header>
  );
}
