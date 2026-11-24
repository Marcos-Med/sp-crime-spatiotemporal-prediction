// Filtros do mapa: tipo de crime, período e município.
import type { FiltroTempo, TipoFiltro } from '../../lib/periodo';
import { anosDisponiveis, nomeMes } from '../../lib/periodo';
import type { AlvoMapa, MetadadosMunicipio } from '../../types/dados';

interface Props {
  filtro: FiltroTempo;
  onFiltro: (f: FiltroTempo) => void;
  meses: string[];
  alvos: AlvoMapa[];
  alvo: string;
  onAlvo: (id: string) => void;
  municipios: MetadadosMunicipio[];
  municipio: string;
  onMunicipio: (codigo: string) => void;
}

const TIPOS: { id: TipoFiltro; nome: string }[] = [
  { id: 'mes', nome: 'Mês' },
  { id: 'ano', nome: 'Ano' },
  { id: 'tudo', nome: '12 meses' },
];

export default function Filtros({ filtro, onFiltro, meses, alvos, alvo, onAlvo, municipios, municipio, onMunicipio }: Props) {
  return (
    <div className="filtros">
      <fieldset className="grupo-filtro">
        <legend>Tipo de crime</legend>
        <div className="segmentado" role="radiogroup" aria-label="Tipo de crime">
          {alvos.map((a) => (
            <button key={a.id} type="button" role="radio" aria-checked={alvo === a.id}
              className={alvo === a.id ? 'ativo' : ''} onClick={() => onAlvo(a.id)}>
              {a.nome}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset className="grupo-filtro">
        <legend>Período</legend>
        <div className="segmentado" role="radiogroup" aria-label="Tipo de período">
          {TIPOS.map((t) => (
            <button key={t.id} type="button" role="radio" aria-checked={filtro.tipo === t.id}
              className={filtro.tipo === t.id ? 'ativo' : ''} onClick={() => onFiltro({ ...filtro, tipo: t.id })}>
              {t.nome}
            </button>
          ))}
        </div>
        {filtro.tipo === 'mes' && (
          <select id="filtro-mes" value={filtro.mes} aria-label="Mês" onChange={(e) => onFiltro({ ...filtro, mes: e.target.value })}>
            {meses.map((m) => <option key={m} value={m}>{nomeMes(m)}</option>)}
          </select>
        )}
        {filtro.tipo === 'ano' && (
          <select id="filtro-ano" value={filtro.ano} aria-label="Ano" onChange={(e) => onFiltro({ ...filtro, ano: Number(e.target.value) })}>
            {anosDisponiveis(meses).map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        )}
      </fieldset>
      <fieldset className="grupo-filtro">
        <legend>Município</legend>
        <select id="filtro-municipio" value={municipio} aria-label="Município" onChange={(e) => onMunicipio(e.target.value)}>
          <option value="">Toda a Grande São Paulo</option>
          {[...municipios].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')).map((m) => (
            <option key={m.codigo} value={m.codigo}>{m.nome}</option>
          ))}
        </select>
      </fieldset>
    </div>
  );
}
