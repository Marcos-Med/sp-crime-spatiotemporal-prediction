"""Gera src/data/municipios.json com dados REAIS da base do Marcos.

Uso:
    python scripts/gerar-municipios.py <pasta do repo do Marcos>/datasets/database_processed_h3_final.csv

O CSV sai do notebook processing_datasets/creating_features_ssp_sp.ipynb (pasta datasets/, fora do GitHub).
Ele tem uma linha por hexágono e mês, com as contagens (CNT_CRIME, FURTO, ROUBO) e os dados do Censo 2022/IPVS
já agregados por hexágono. Esses dados do Censo são MÉDIAS dos setores censitários de cada hexágono, então aqui
só calculamos médias (IPVS, alfabetização, jovens). Somar população daria um número sem sentido.
"""
import json
import sys
import unicodedata
from pathlib import Path

import h3
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CONTORNOS = RAIZ / 'src' / 'geo' / 'rmsp-municipios.json'
SAIDA = RAIZ / 'src' / 'data' / 'municipios.json'

# Abreviações usadas pela SSP-SP no nome das cidades
APELIDOS = {
    'S.PAULO': 'SAO PAULO',
    'S.ANDRE': 'SANTO ANDRE',
    'S.BERNARDO DO CAMPO': 'SAO BERNARDO DO CAMPO',
    'S.CAETANO DO SUL': 'SAO CAETANO DO SUL',
    'S.LOURENCO DA SERRA': 'SAO LOURENCO DA SERRA',
    'PIRAPORA BOM JESUS': 'PIRAPORA DO BOM JESUS',
    'MOJI DAS CRUZES': 'MOGI DAS CRUZES',
    'EMBU': 'EMBU DAS ARTES',
}


def normalizar(nome: str) -> str:
    s = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode().upper().strip()
    return APELIDOS.get(s, s)


def dentro_da_rmsp(hexes) -> set:
    """Hexágonos cujo centro cai dentro do contorno da RMSP.

    A base do modelo filtra a região pelo nome da cidade do boletim, não pela coordenada. Por erro de geocodificação,
    52 das 1.260 células ficam no interior do estado (89 ocorrências, 0,003%). A página não mostra essas células.
    """
    from shapely.geometry import Point, shape
    from shapely.ops import unary_union
    geo = json.loads(CONTORNOS.read_text(encoding='utf-8'))
    regiao = unary_union([shape(f['geometry']) for f in geo['features']]).buffer(0.02)  # ~2 km de folga na borda
    return {h for h in hexes if regiao.contains(Point(h3.cell_to_latlng(h)[::-1]))}


def em_porcentagem(serie: pd.Series) -> pd.Series:
    # aceita a coluna em fração (0 a 1) ou já em %
    return serie * 100 if serie.max() <= 1 else serie


def arred(v, casas=1):
    return None if pd.isna(v) else round(float(v), casas)


def main(caminho: str) -> None:
    colunas = ['H3', 'CIDADE', 'CNT_CRIME', 'FURTO', 'ROUBO', 'C_IPVS', 'taxa_alfabetizacao', 'pct_jovens_15_29']
    df = pd.read_csv(caminho, usecols=colunas, low_memory=False)
    dentro = dentro_da_rmsp(df.H3.unique())
    print(f'{df.H3.nunique() - len(dentro)} hexágonos fora da RMSP removidos '
          f'({int(df.loc[~df.H3.isin(dentro), "CNT_CRIME"].sum())} ocorrências)')
    df = df[df.H3.isin(dentro)]

    # uma linha por hexágono: ocorrências somadas no período todo; Censo/IPVS são fixos por hexágono
    hex_ = df.groupby('H3').agg(
        CIDADE=('CIDADE', lambda s: s.mode().iloc[0] if not s.mode().empty else None),
        crime=('CNT_CRIME', 'sum'), furto=('FURTO', 'sum'), roubo=('ROUBO', 'sum'),
        ipvs=('C_IPVS', 'first'), alfab=('taxa_alfabetizacao', 'first'), jovens=('pct_jovens_15_29', 'first'),
    ).reset_index()
    hex_['alfab'] = em_porcentagem(hex_['alfab'])
    hex_['jovens'] = em_porcentagem(hex_['jovens'])
    hex_['area'] = [h3.cell_area(h, 'km^2') for h in hex_['H3']]

    geo = json.loads(CONTORNOS.read_text(encoding='utf-8'))
    codigo_por_nome = {normalizar(f['properties']['nome']): f['properties']['codigo'] for f in geo['features']}
    hex_['codigo'] = hex_['CIDADE'].map(lambda c: codigo_por_nome.get(normalizar(c)) if pd.notna(c) else None)

    sem_municipio = hex_[hex_['codigo'].isna()]
    if len(sem_municipio):
        print(f'ATENÇÃO: {len(sem_municipio)} hexágonos com cidade fora da lista:',
              sorted(sem_municipio['CIDADE'].dropna().unique())[:20])

    municipios = []
    for f in geo['features']:
        codigo, nome = f['properties']['codigo'], f['properties']['nome']
        g = hex_[hex_['codigo'] == codigo]
        municipios.append({
            'codigo': codigo,
            'nome': nome,
            'hexagonos': int(len(g)),
            'areaKm2': round(float(g['area'].sum())),
            'crimes': {'total': int(g['crime'].sum()), 'furto': int(g['furto'].sum()), 'roubo': int(g['roubo'].sum())},
            'ipvsMedio': arred(g['ipvs'].mean()),
            'taxaAlfabetizacao': arred(g['alfab'].mean()),
            'pctJovens15a29': arred(g['jovens'].mean()),
        })

    SAIDA.write_text(json.dumps(municipios, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'ok: {SAIDA.name} | {len(hex_)} hexágonos, {int(hex_["crime"].sum()):,} ocorrências, '
          f'{sum(m["hexagonos"] > 0 for m in municipios)} municípios com dados')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
