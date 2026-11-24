export default function Rodape() {
  return (
    <footer className="rodape">
      <div className="rodape-int">
        <p><strong>Mapa de Risco SP</strong> · Projeto RP2</p>
        <p>Previsão de risco por hexágono H3. Ocorrências: SSP-SP (2022 a jun/2026). Perfil dos bairros: Censo IBGE 2022 e IPVS. Contornos municipais: IBGE. Mapa de fundo: OpenFreeMap e OpenStreetMap.</p>
        <p className="rodape-mock">Os números vêm do artigo final do grupo e da base e dos resultados do repositório sp-crime-spatiotemporal-prediction. O mapa mostra as previsões do teste (jul/2025 a jun/2026).</p>
      </div>
    </footer>
  );
}
