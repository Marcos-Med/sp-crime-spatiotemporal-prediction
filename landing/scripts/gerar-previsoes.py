"""Gera src/data/previsoes.json e completa src/data/metricas.json.

Uso: python scripts/gerar-previsoes.py <pasta datasets>
"""
import importlib.util
import json
import math
import sys
from datetime import date
from pathlib import Path

import h3
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA_PREV = RAIZ / 'src' / 'data' / 'previsoes.json'
METRICAS = RAIZ / 'src' / 'data' / 'metricas.json'

ALVOS = [
    ('crime', 'RISCO_CRIME', 'CNT_CRIME_COUNT', 'Crime total'),
    ('furto', 'RISCO_FURTO', 'FURTO_COUNT', 'Furto'),
    ('roubo', 'RISCO_ROUBO', 'ROUBO_COUNT', 'Roubo'),
]
REFERENCIAS = {'ewm3': 'EWM3', 'media_hex': 'media_historica_fixa'}
REFERENCIAS_VALIDACAO = {**REFERENCIAS, 'ridge': 'Ridge_resid_alto_HurdleNB_baixo'}
FATIA_PAI = 0.05

_spec = importlib.util.spec_from_file_location('mun', RAIZ / 'scripts' / 'gerar-municipios.py')
mun = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mun)


def celulas_com_imputacao(d: Path) -> set:
    f = d / 'database_processed_h3.csv'
    if not f.exists():
        print(f'aviso: {f.name} não encontrado; células com coordenadas imputadas não serão marcadas')
        return set()
    b = pd.read_csv(f, usecols=['LATITUDE', 'LONGITUDE', 'CIDADE', 'CNT_CRIME', 'H3'], low_memory=False)
    pontos = b.groupby(['CIDADE', 'LATITUDE', 'LONGITUDE', 'H3'], as_index=False).CNT_CRIME.sum()
    topo = pontos.loc[pontos.groupby('CIDADE').CNT_CRIME.idxmax()].copy()
    topo['fracao'] = topo.CNT_CRIME / topo.H3.map(b.groupby('H3').CNT_CRIME.sum())
    marcadas = topo[topo.fracao >= 0.3]
    print(f'{len(marcadas)} hexágonos marcados por concentrar ocorrências sem endereço exato '
          f'({int(marcadas.CNT_CRIME.sum()):,} ocorrências nesses pontos)')
    return set(marcadas.H3)


def pai(df: pd.DataFrame, col_pred: str, col_real: str, area: pd.Series) -> float:
    valores = []
    for _, m in df.groupby('DATA'):
        n = max(1, math.ceil(FATIA_PAI * len(m)))
        topo = m.nlargest(n, col_pred)
        total = m[col_real].sum()
        if total <= 0:
            continue
        frac_crimes = topo[col_real].sum() / total
        frac_area = area.loc[topo.H3].sum() / area.loc[m.H3].sum()
        valores.append(frac_crimes / frac_area)
    return round(sum(valores) / len(valores), 2)


def main(pasta: str) -> None:
    d = Path(pasta)
    pred = pd.read_csv(d / 'final_model_comparison_groups_h3_predictions.csv', parse_dates=['DATA'], low_memory=False)
    validacao = pred[pred.particao.eq('validacao_temporal')]
    pred = pred[pred.particao.eq('teste_reservado')]
    resumo = pd.read_csv(d / 'final_model_comparison_groups_h3_summary.csv')
    teste = resumo[resumo.avaliacao.eq('teste_reservado')]
    cols_real = [c for _, _, c, _ in ALVOS]
    real = pd.read_csv(d / 'database_processed_h3_risk.csv', usecols=['H3', 'DATA', 'CIDADE', *cols_real],
                       parse_dates=['DATA'], low_memory=False)

    meses = sorted(pred.DATA.unique())
    nomes_meses = [pd.Timestamp(m).strftime('%Y-%m') for m in meses]
    hexes = sorted(pred.H3.unique())
    area = pd.Series({h: h3.cell_area(h, 'km^2') for h in hexes})

    geo = json.loads(mun.CONTORNOS.read_text(encoding='utf-8'))
    codigo_por_nome = {mun.normalizar(f['properties']['nome']): f['properties']['codigo'] for f in geo['features']}
    cidade = real.groupby('H3').CIDADE.agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
    municipio = {h: codigo_por_nome.get(mun.normalizar(cidade.get(h))) for h in hexes}
    imputadas = celulas_com_imputacao(d)
    na_regiao = mun.dentro_da_rmsp(hexes)
    print(f'{len(hexes) - len(na_regiao)} hexágonos fora da RMSP ficam fora do mapa')
    sem = [h for h, c in municipio.items() if c is None]
    if sem:
        print(f'ATENÇÃO: {len(sem)} hexágonos sem município reconhecido')

    risco = {h: {} for h in hexes}
    metricas = json.loads(METRICAS.read_text(encoding='utf-8'))
    for alvo_id, alvo, col_real, nome in ALVOS:
        linhas_teste = teste[teste.target.eq(alvo)]
        escolhido = linhas_teste.modelo_selecionado_validacao.iloc[0]
        col_pred = f'pred_{escolhido}'
        p = pred[pred.target.eq(alvo)].merge(real[['H3', 'DATA', col_real]], on=['H3', 'DATA'], how='left')
        tabela = p.pivot(index='H3', columns='DATA', values=col_pred).reindex(index=hexes, columns=meses)
        for h, linha in tabela.iterrows():
            risco[h][alvo_id] = [round(min(1.0, max(0.0, float(v))), 3) for v in linha]

        bloco = next(a for a in metricas['alvos'] if a['id'] == alvo_id)
        por_modelo = linhas_teste.set_index('modelo')
        for m in bloco['modelos']:
            nome_modelo = escolhido if m['id'] == 'escolhido' else REFERENCIAS.get(m['id'])
            if nome_modelo is None:
                continue
            r = por_modelo.loc[nome_modelo]
            m['metricas'] = {'r2': round(float(r.R2_risco_medio), 4), 'mae': round(float(r.MAE_risco_medio), 4),
                             'rmse': round(float(r.RMSE_risco_medio), 4), 'pai': pai(p, f'pred_{nome_modelo}', col_real, area)}
            if m['id'] != 'escolhido':
                m['descricao'] = 'Referência, no mesmo teste.'
        print(f'{nome}: modelo {escolhido} | PAI {FATIA_PAI:.0%} no teste = ' +
              ', '.join(f"{m['id']} {m['metricas']['pai']}" for m in bloco['modelos']))

        pv = validacao[validacao.target.eq(alvo)].merge(real[['H3', 'DATA', col_real]], on=['H3', 'DATA'], how='left')
        for tabela_extra in metricas.get('tabelasExtras', []):
            bloco_v = next((a for a in tabela_extra['alvos'] if a['id'] == alvo_id), None)
            for m in (bloco_v or {}).get('modelos', []):
                nome_modelo = escolhido if m['id'] == 'escolhido' else REFERENCIAS_VALIDACAO.get(m['id'])
                if nome_modelo:
                    m['metricas']['pai'] = pai(pv, f'pred_{nome_modelo}', col_real, area)
            if bloco_v:
                print(f'{nome}: PAI {FATIA_PAI:.0%} na validação = ' +
                      ', '.join(f"{m['id']} {m['metricas']['pai']}" for m in bloco_v['modelos']))

    saida = {
        'fonte': 'modelo',
        'geradoEm': date.today().isoformat(),
        'resolucaoH3': 7,
        'unidade': 'nota de risco de 0 a 1 por hexágono e por mês (modelo escolhido na validação, teste reservado)',
        'meses': nomes_meses,
        'alvos': [{'id': a, 'nome': n} for a, _, _, n in ALVOS],
        'hexagonos': [{'h3': h, 'municipio': municipio[h], 'risco': risco[h], **({'imputado': True} if h in imputadas else {})}
                      for h in hexes if municipio[h] and h in na_regiao],
    }
    SAIDA_PREV.write_text(json.dumps(saida, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'ok: {SAIDA_PREV.name} ({len(saida["hexagonos"])} hexágonos, {len(meses)} meses) e {METRICAS.name} atualizado')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
