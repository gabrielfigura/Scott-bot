import asyncio
import aiohttp
import logging
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from collections import Counter
import uuid

# Configurações do Bot (valores fixos para teste)
BOT_TOKEN = "8003298514:AAEP-T_vzKjoXL3dwuq7hZWgzbKZpFvZgSg"
CHAT_ID = "-1002786621018"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = []
ultimo_padrao_id = None
ultimo_resultado_id = None
sinais_ativos = []
placar = {
    "ganhos_seguidos": 0,
    "ganhos_gale1": 0,
    "ganhos_gale2": 0,
    "losses": 0,
    "empates": 0   # 👈 Novo campo para empates
}
rodadas_desde_erro = 0
ultima_mensagem_monitoramento = None
detecao_pausada = False
aguardando_validacao = False  # Nova flag para bloquear novos sinais até validação

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

# Padrões
PADROES = [
 { "id": 1, "sequencia": ["🔵", "🔴", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 2, "sequencia": ["🔴", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 3, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 4, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 5, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 6, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 7, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 8, "sequencia": ["🔵", "🔴", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 9, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 10, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 11, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 12, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 13, "sequencia": ["🔵", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 14, "sequencia": ["🔴", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 15, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 16, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 17, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 18, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 19, "sequencia": ["🔴", "🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 20, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 21, "sequencia": ["🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 22, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 23, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 24, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 25, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 26, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 27, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 28, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 29, "sequencia": ["🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 30, "sequencia": ["🔴", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 31, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 32, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 33, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 34, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 35, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 36, "sequencia": ["🔵", "🔴", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 37, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 38, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 39, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 40, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 41, "sequencia": ["🔵", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 42, "sequencia": ["🔴", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 43, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 44, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 45, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 46, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 47, "sequencia": ["🔴", "🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 48, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 49, "sequencia": ["🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 50, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 51, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 52, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 53, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 54, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 55, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 56, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 57, "sequencia": ["🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 58, "sequencia": ["🔴", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 59, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 60, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 61, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 62, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 63, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 64, "sequencia": ["🔵", "🔴", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 65, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 66, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 67, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 68, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 69, "sequencia": ["🔵", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 70, "sequencia": ["🔴", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 71, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 72, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 73, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 74, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 75, "sequencia": ["🔴", "🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 76, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 77, "sequencia": ["🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 78, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 79, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 80, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 81, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 82, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 83, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 84, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 85, "sequencia": ["🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 86, "sequencia": ["🔴", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 87, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 88, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 89, "sequencia": ["🔵", "🔵", "🔴"], "sinal": "🔵" },
  { "id": 90, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 91, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "sinal": "🔴" },
  { "id": 92, "sequencia": ["🔵", "🔴", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 93, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 94, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵" },
  { "id": 95, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 96, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔴" },
  { "id": 97, "sequencia": ["🔵", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 98, "sequencia": ["🔴", "🔵", "🔵", "🔵"], "sinal": "🔵" },
  { "id": 99, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴" },
  { "id": 100, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵" }
]

@retry(stop=stop_after_attempt(7), wait=wait_exponential(multiplier=1, min=4, max=60), retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)))
async def fetch_resultado():
    """Busca o resultado mais recente da API com retry e timeout aumentado."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None, None, None, None
                data = await response.json()
                if 'data' not in data or 'result' not in data['data'] or 'outcome' not in data['data']['result']:
                    return None, None, None, None
                if 'id' not in data:
                    return None, None, None, None
                if data['data'].get('status') != 'Resolved':
                    return None, None, None, None
                resultado_id = data['id']
                outcome = data['data']['result']['outcome']
                player_score = data['data']['result'].get('playerDice', {}).get('score', 0)
                banker_score = data['data']['result'].get('bankerDice', {}).get('score', 0)
                if outcome not in OUTCOME_MAP:
                    return None, None, None, None
                resultado = OUTCOME_MAP[outcome]
                return resultado, resultado_id, player_score, banker_score
        except:
            return None, None, None, None

def verificar_tendencia(historico, sinal, tamanho_janela=8):
    if len(historico) < tamanho_janela:
        return True
    janela = historico[-tamanho_janela:]
    contagem = Counter(janela)
    total = contagem["🔴"] + contagem["🔵"]
    if total == 0:
        return True
    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, padrao_id, resultado_id, sequencia):
    global ultima_mensagem_monitoramento, aguardando_validacao
    try:
        if ultima_mensagem_monitoramento:
            try:
                await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
            except TelegramError:
                pass
            ultima_mensagem_monitoramento = None
        if aguardando_validacao or sinais_ativos:
            logging.info(f"Sinal bloqueado: aguardando validação ou sinal ativo (ID: {padrao_id})")
            return False
        sequencia_str = " ".join(sequencia)
        mensagem = f"""💡 ENTRA COM SCOTT💡
🧠 APOSTA EM: {sinal}
🛡️ Proteja o EMPATE 🟡
🤑 MBORA GANHAR 🤑"""
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        sinais_ativos.append({
            "sinal": sinal,
            "padrao_id": padrao_id,
            "resultado_id": resultado_id,
            "sequencia": sequencia,
            "enviado_em": asyncio.get_event_loop().time(),
            "gale_nivel": 0,
            "gale_message_id": None
        })
        aguardando_validacao = True  # Bloqueia novos sinais até validação
        logging.info(f"Sinal enviado para padrão {padrao_id}: {sinal}")
        return message.message_id
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

async def resetar_placar():
    global placar
    placar = {
        "ganhos_seguidos": 0,
        "ganhos_gale1": 0,
        "ganhos_gale2": 0,
        "losses": 0,
        "empates": 0
    }
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🔄 Placar resetado após 10 erros! Começando do zero.")
        await enviar_placar()
    except TelegramError:
        pass

async def enviar_placar():
    try:
        total_acertos = placar['ganhos_seguidos'] + placar['ganhos_gale1'] + placar['ganhos_gale2'] + placar['empates']
        total_sinais = total_acertos + placar['losses']
        precisao = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0.0
        precisao = min(precisao, 100.0)
        mensagem_placar = f"""🚀 PLACAR DI SCOTT 🚀
✅SEM GALE: {placar['ganhos_seguidos']}
🔁GALE 1: {placar['ganhos_gale1']}
🔁GALE 2: {placar['ganhos_gale2']}
🟡EMPATES: {placar['empates']}
🎯ACERTOS: {total_acertos}
❌ERROS: {placar['losses']}
🔥PRECISÃO: {precisao:.2f}%"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem_placar)
    except TelegramError:
        pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    global rodadas_desde_erro, ultima_mensagem_monitoramento, detecao_pausada, placar, ultimo_padrao_id, aguardando_validacao
    try:
        for sinal_ativo in sinais_ativos[:]:
            if sinal_ativo["resultado_id"] != resultado_id:
                if resultado == sinal_ativo["sinal"] or resultado == "🟡":
                    if resultado == "🟡":
                        placar["empates"] += 1
                    if sinal_ativo["gale_nivel"] == 0:
                        placar["ganhos_seguidos"] += 1
                    elif sinal_ativo["gale_nivel"] == 1:
                        placar["ganhos_gale1"] += 1
                    else:
                        placar["ganhos_gale2"] += 1
                    if sinal_ativo["gale_message_id"]:
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        except TelegramError:
                            pass
                    mensagem_validacao = f" 🔥GANHAMOS🔥\n🎲 Resultado: 🔵 {player_score} x 🔴 {banker_score}"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    await enviar_placar()
                    ultimo_padrao_id = None
                    aguardando_validacao = False  # Libera para novos sinais
                    sinais_ativos.remove(sinal_ativo)
                    detecao_pausada = False
                    logging.info(f"Sinal validado com sucesso para padrão {sinal_ativo['padrao_id']}")
                else:
                    if sinal_ativo["gale_nivel"] == 0:
                        detecao_pausada = True
                        mensagem_gale = "🔄 Tentar 1º Gale"
                        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem_gale)
                        sinal_ativo["gale_nivel"] = 1
                        sinal_ativo["gale_message_id"] = message.message_id
                        sinal_ativo["resultado_id"] = resultado_id
                    elif sinal_ativo["gale_nivel"] == 1:
                        detecao_pausada = True
                        mensagem_gale = "🔄 Tentar 2º Gale"
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        except TelegramError:
                            pass
                        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem_gale)
                        sinal_ativo["gale_nivel"] = 2
                        sinal_ativo["gale_message_id"] = message.message_id
                        sinal_ativo["resultado_id"] = resultado_id
                    else:
                        placar["losses"] += 1
                        if sinal_ativo["gale_message_id"]:
                            try:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                            except TelegramError:
                                pass
                        await bot.send_message(chat_id=CHAT_ID, text="❌ ERRAMOS ESSA❌")
                        await enviar_placar()
                        # Verifica limite de erros e reseta placar se necessário
                        if placar["losses"] >= 10:
                            await resetar_placar()
                        ultimo_padrao_id = None
                        aguardando_validacao = False  # Libera para novos sinais mesmo em perda
                        sinais_ativos.remove(sinal_ativo)
                        detecao_pausada = False
                        logging.info(f"Sinal perdido para padrão {sinal_ativo['padrao_id']}, validação liberada")
                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                if sinal_ativo["gale_message_id"]:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                    except TelegramError:
                        pass
                ultimo_padrao_id = None
                aguardando_validacao = False
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
                logging.info(f"Sinal expirado para padrão {sinal_ativo['padrao_id']}, validação liberada")
        # Se não há sinais ativos, libera a flag
        if not sinais_ativos:
            aguardando_validacao = False
    except TelegramError:
        pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_monitoramento():
    global ultima_mensagem_monitoramento
    while True:
        try:
            if not sinais_ativos:
                if ultima_mensagem_monitoramento:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
                    except TelegramError:
                        pass
                message = await bot.send_message(chat_id=CHAT_ID, text="🧠ANALISANDO…")
                ultima_mensagem_monitoramento = message.message_id
            await asyncio.sleep(15)
        except TelegramError:
            await asyncio.sleep(15)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_relatorio():
    while True:
        try:
            total_acertos = placar['ganhos_seguidos'] + placar['ganhos_gale1'] + placar['ganhos_gale2'] + placar['empates']
            total_sinais = total_acertos + placar['losses']
            precisao = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0.0
            precisao = min(precisao, 100.0)
            msg = f"""🚀 PLACAR DO SCOTT🚀
✅SEM GALE: {placar['ganhos_seguidos']}
🔁GALE 1: {placar['ganhos_gale1']}
🔁GALE 2: {placar['ganhos_gale2']}
🟡EMPATES: {placar['empates']}
🎯ACERTOS: {total_acertos}
❌ERROS: {placar['losses']}
🔥PRECISÃO: {precisao:.2f}%"""
            await bot.send_message(chat_id=CHAT_ID, text=msg)
        except TelegramError:
            pass
        await asyncio.sleep(3600)

async def enviar_erro_telegram(erro_msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro detectado: {erro_msg}")
    except TelegramError:
        pass

async def main():
    global historico, ultimo_padrao_id, ultimo_resultado_id, rodadas_desde_erro, detecao_pausada, aguardando_validacao
    asyncio.create_task(enviar_relatorio())
    asyncio.create_task(enviar_monitoramento())
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot iniciado com sucesso!")
    except TelegramError:
        pass
    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if not resultado or not resultado_id:
                await asyncio.sleep(2)
                continue
            if resultado_id == ultimo_resultado_id:
                await asyncio.sleep(2)
                continue
            ultimo_resultado_id = resultado_id
            historico.append(resultado)
            if len(historico) > 50:
                historico.pop(0)
            await enviar_resultado(resultado, player_score, banker_score, resultado_id)
            # Só verifica padrões se não estiver pausado, sem sinais ativos e aguardando validação
            if not detecao_pausada and not aguardando_validacao and not sinais_ativos:
                for padrao in PADROES:
                    seq_len = len(padrao["sequencia"])
                    if len(historico) >= seq_len:
                        if historico[-seq_len:] == padrao["sequencia"] and padrao["id"] != ultimo_padrao_id:
                            if verificar_tendencia(historico, padrao["sinal"]):
                                enviado = await enviar_sinal(padrao["sinal"], padrao["id"], resultado_id, padrao["sequencia"])
                                if enviado:
                                    ultimo_padrao_id = padrao["id"]
                                    break  # Para após enviar o primeiro sinal válido
            await asyncio.sleep(2)
        except Exception as e:
            await enviar_erro_telegram(str(e))
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no bot: {e}")
        asyncio.run(enviar_erro_telegram(f"Erro fatal no bot: {e}"))
