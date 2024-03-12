
from flask import Flask, jsonify
import requests

app = Flask(__name__)

def formatar_cotacoes(eventos):
    for evento in eventos:
        if 'subeventos' in evento:
            for subevento in evento['subeventos']:
                if 'cotacao' in subevento:
                    subevento['cotacao'] = float(subevento['cotacao']) / 100  # Converta para decimal com um ponto
    return eventos

def consultar_eventos(torneio):
    url = 'https://www.betsul.com/web/v2/eventos'
    headers = {
        'authority': 'www.betsul.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'pt-br',
        'content-type': 'application/json',
        'origin': 'https://www.betsul.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
 }

    data = {
        'type': 'prematch',
        'filters': {
            'tipoEsporte': 1,
            'torneio': torneio,
            'iniciado': True
        },
        'limit': 30,
        'include': [],
        'sort': ['date-asc']
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Lança exceção para códigos de status diferentes de 2xx
        eventos = response.json()
        return formatar_cotacoes(eventos.get('eventos', []))
    except requests.exceptions.RequestException as e:
        return {'error': f'Erro na requisição: {str(e)}'}

@app.route('/consultar_liga_campeoes', methods=['GET'])
def consultar_liga_campeoes():
    return jsonify(consultar_eventos('liga-dos-campeoes-da-uefa'))

@app.route('/consultar_copa_libertadores', methods=['GET'])
def consultar_copa_libertadores():
    return jsonify(consultar_eventos('copa-libertadores'))


@app.route('/consultar_copa_brasil', methods=['GET'])
def consultar_copa_brasil():
    return jsonify(consultar_eventos('copa-do-brasil'))

@app.route('/consultar_carioca_taca_guanabara', methods=['GET'])
def consultar_carioca_taca_guanabara():
    return jsonify(consultar_eventos('Carioca - Taça Guanabara'))

@app.route('/consultar_campeonato_mineiro', methods=['GET'])
def consultar_campeonato_mineiro():
    return jsonify(consultar_eventos('mineiro'))

@app.route('/consultar_campeonato_goiano', methods=['GET'])
def consultar_campeonato_goiano():
    return jsonify(consultar_eventos('goiano'))

@app.route('/consultar_campeonato_capixaba', methods=['GET'])
def consultar_campeonato_capixaba():
    return jsonify(consultar_eventos('Capixaba'))


@app.route('/consultar_campeonato_paranaense', methods=['GET'])
def consultar_campeonato_paranaense():
    return jsonify(consultar_eventos('Paranaense'))

@app.route('/consultar_aovivo', methods=['GET'])
def consultar_aovivo():
    return jsonify(consultar_eventos(''))
    
@app.route('/consultar_premier_league', methods=['GET'])
def consultar_premier_league():
    return jsonify(consultar_eventos('premier-league'))



if __name__ == '__main__':
    app.run(debug=True)
              
