from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters 
from analisis import analizar_mensaje, responder_con_ia
from telegram import Update 
from config import TOKEN, KEY_OPENAI
from io import BytesIO
import tempfile
import os
from pydub import AudioSegment
from openai import OpenAI
from datetime import datetime

client = OpenAI(KEY_OPENAI)
conversaciones = {}
limite_audios_por_dia = 2
uso_usuarios = {}
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = update.effective_user
    nombre = usuario.first_name or ""
    await update.message.reply_text(
                                    f"¡Hola {f'{nombre}' if nombre else ''}! ¿Cómo estás?\n"
                                    "Soy tu asistente de viajes\n\n"
                                    "Podes enviarme mensajes de texto o audios para obtener información sobre:\n"
                                    "• Alojamientos\n"
                                    "• Destinos y ciudades\n"
                                    "• Atracciones\n\n"
                                    "Para optimizar los recursos que dispongo, los audios tienen un límite diario de 2 por usuario con una duración menor a 1 minuto.\n"
                                    "Podés seguir consultando por texto sin problema alguno 😊\n\n"
                                    "¿En qué puedo ayudarte?"
                                )

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def gestion_de_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.message.chat_id
    await update.message.reply_chat_action("typing")
    
    if update.message.voice:
        try:
            await update.message.reply_text("🎧 Procesando tu audio...")
            user_id = update.effective_user.id
            hoy = datetime.now().date()
            if user_id not in uso_usuarios:
                uso_usuarios[user_id] = {"fecha": hoy, "cantidad": 0}
            if uso_usuarios[user_id]["fecha"] != hoy:
                uso_usuarios[user_id] = {"fecha": hoy, "cantidad": 0}
            if uso_usuarios[user_id]["cantidad"] >= limite_audios_por_dia:
                await update.message.reply_text(
                    "Alcanzaste el límite diario de audios. Podés seguir escribiendo conmigo por texto 😊"
                )
                return
            if update.message.voice.duration > 60:
                await update.message.reply_text(
                    "El audio supera el máximo de 1 minuto. Porfavor intentá con uno más corto 😊"
                )
                return
            uso_usuarios[user_id]["cantidad"] += 1
            
            file = await context.bot.get_file(update.message.voice.file_id)
            ogg_buffer = BytesIO()
            await file.download_to_memory(out=ogg_buffer)
            ogg_buffer.seek(0)
            
            audio = AudioSegment.from_file(ogg_buffer, format="ogg")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                audio.export(tmp_wav.name, format="wav")
                tmp_wav_path = tmp_wav.name
            
            with open(tmp_wav_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="gpt-4o-transcribe",
                    file=audio_file
                )
            texto = transcription.text.strip()
        except Exception as e:
            print("Error procesando el audio:", e)
            await update.message.reply_text("Ocurrió un error procesando el audio. ¿Podés repetirlo por favor?")
            return
        finally:
            if 'tmp_wav_path' in locals() and os.path.exists(tmp_wav_path):
                os.remove(tmp_wav_path)
    elif update.message.text:
        texto = update.message.text.strip()
    else:
        await update.message.reply_text("No reconozco el formato del mensaje")
        return
    
    if chat_id not in conversaciones:
        conversaciones[chat_id] = {
            "estado": "nuevo",
            "datos": {},
        }
    contexto = conversaciones[chat_id]
    
    analisis, contexto = analizar_mensaje(texto, contexto)
     
    datos_previos = contexto.get("datos", {})
    for clave, valor in analisis.items():
        if valor not in [None, "", [], {}]:
            datos_previos[clave] = valor
    contexto["datos"] = datos_previos

    if analisis:
        respuesta, contexto = responder_con_ia(analisis, contexto)
    else:
        respuesta = "No entendí bien tu consulta. ¿Podrías explicarlo de otra forma?"
        contexto["estado"] = "en_progreso"
    await update.message.reply_text(respuesta)
    
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def main(): 
    app = ApplicationBuilder().token(TOKEN).build() 
    app.add_handler(CommandHandler("start", start)) 
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^h*o+la*'), start))
    app.add_handler(MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, gestion_de_consulta))
    
    print("Esperando mensajes...") 
    app.run_polling() 
    
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

if __name__== "__main__": 
    main()