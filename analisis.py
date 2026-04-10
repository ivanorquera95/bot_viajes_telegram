from funciones import buscar_vuelos,buscar_lugares,generar_links
from openai import OpenAI
from config import KEY_OPENAI
import json

client = OpenAI(KEY_OPENAI)

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def analizar_mensaje(texto, contexto):
    prompt = f"""
                Sos un asistente inteligente de viajes que trabaja con APIs.
                Tu tarea es analizar el mensaje del usuario y devolver un JSON estructurado que permita decidir qué función ejecutar.
                IMPORTANTE:
                - Pensá en términos de APIs disponibles:
                    1) "vuelos" → búsqueda de vuelos (Amadeus)
                    2) "lugares" → restaurantes, atracciones, turismo (Google Maps)
                    3) "alojamientos" → hoteles, departamentos, etc.
                    4) "autos" → alquiler de autos
                    5) "paquetes" → viajes completos
                    6) "general" → consultas abiertas
                    7) "despedida"  → mensaje de depedida

                Tenés que identificar:
                1) tipo_consulta → lista de:["vuelos", "lugares", "alojamientos", "autos", "paquetes", "general"]
                2) categoria → UNA sola si aplica: "hoteles" | "apartamentos" | "casas" | "hostales" | "campings" | "restaurantes" | "atracciones" | "alquiler_autos" | ""
                3) consulta → texto original
                4) origen → ciudad/país de salida si existe
                5) destinos → lista de lugares mencionados
                6) fechas: fecha_inicio | fecha_fin
                7) pasajeros:- cantidad_personas | cantidad_habitaciones (default = "1")
                8) vuelo:- vuelo_tipo: "solo_ida" | "ida_vuelta" | "multidestino" | "" 
                vuelo_clase: "economica" | "premium_economy" | "business" | "primera" | ""
                9) depedida: si el usuario dice gracias, , chau , adios , nos vemos, etc y sin nada mas. IMPORTANTE: sin alguna otra pregunta, despedirte calidamente.
                REGLAS:
                - SIEMPRE devolver JSON válido
                - NO agregar texto fuera del JSON
                - NO inventar datos
                - Si no está claro → usar "general"

                Formato:
                {{
                "tipo_consulta": [],
                "categoria": "",
                "consulta": "{texto}",
                "fecha_inicio": "",
                "fecha_fin": "",
                "cantidad_personas": "",
                "cantidad_habitaciones": "1",
                "origen": "",
                "destinos": [],
                "vuelo_tipo": "",
                "vuelo_clase": ""
                }}
                Ejemplos:
                "¿Qué puedo hacer en Rosario?"→ {{"tipo_consulta": ["lugares"],"categoria": "atracciones","consulta": "¿Qué puedo hacer en Rosario?","origen": "", "destinos": ["Rosario"]}}
                "Busco restaurantes en Mendoza"→ {{"tipo_consulta": ["lugares"],"categoria": "restaurantes", "consulta": "Busco restaurantes en Mendoza", "destinos": ["Mendoza"]}}
                "Quiero viajar a Bariloche"→ {{ "tipo_consulta": ["vuelos", "paquetes"],"categoria": "", "consulta": "Quiero viajar a Bariloche", "origen": "", "destinos": ["Bariloche"]}}
                "Vuelos de Buenos Aires a Madrid en clase ejecutiva"→ {{ "tipo_consulta": ["vuelos"], "categoria": "", "consulta": "Vuelos de Buenos Aires a Madrid", "origen": "Buenos Aires", "destinos": ["Madrid"],"vuelo_tipo": "ida_vuelta", "vuelo_clase": "business"}}
                "Hoteles en Salta para 4 personas"→ {{"tipo_consulta": ["alojamientos"], "categoria": "hoteles", "consulta": "Hoteles en Salta", "cantidad_personas": "4", "destinos": ["Salta"]}}
                "gracias" → {{"tipo_consulta": ["despedida"]"categoria": "","consulta": "gracias": "", "destinos":""}}
                "gracias , si que me sugeris para hacer en buenos aires"{{"tipo_consulta": ["lugares"],"categoria": "atracciones","consulta": "gracias , si que me sugeris para hacer en buenos aires": "", "destinos": ["Buenos Aires"]}}
                Mensaje del usuario:
                "{texto}"
                """

    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        salida = respuesta.choices[0].message.content.strip()

        try:
            datos = json.loads(salida)
        except json.JSONDecodeError:
            print("JSON inválido:", salida)
            datos = {"tipo_consulta": ["general"],"categoria": "","consulta": texto,"fecha_inicio": "","fecha_fin": "","cantidad_personas": "","cantidad_habitaciones": "1","origen": "","destinos": [],"vuelo_tipo": "","vuelo_clase": ""}

    except Exception as e:
        print("Error analizando consulta:", e)
        datos = {"tipo_consulta": ["general"],"categoria": "","consulta": texto,"fecha_inicio": "","fecha_fin": "","cantidad_personas": "","cantidad_habitaciones": "1","origen": "","destinos": [],"vuelo_tipo": "","vuelo_clase": ""}

    if isinstance(datos.get("tipo_consulta"), str):
        datos["tipo_consulta"] = [datos["tipo_consulta"]]

    datos.setdefault("categoria", "")
    datos.setdefault("fecha_inicio", "")
    datos.setdefault("fecha_fin", "")
    datos.setdefault("cantidad_personas", "")
    datos.setdefault("cantidad_habitaciones", "1")
    datos.setdefault("origen", "")
    datos.setdefault("destinos", [])
    datos.setdefault("vuelo_tipo", "")
    datos.setdefault("vuelo_clase", "")

    if not isinstance(datos["destinos"], list):
        datos["destinos"] = [datos["destinos"]]

    contexto["estado"] = "en_progreso"
    return datos, contexto

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def responder_con_ia(datos, contexto, historial):
    tipo_consulta = datos.get("tipo_consulta", [])
    
    if "despedida" in tipo_consulta:
        mensaje_final = "¡Gracias! 😊 Fue un gusto ayudarte con tu viaje ✈️🌍"
        return mensaje_final, contexto

    resultados = {}
    try:
        if "vuelos" in tipo_consulta or "paquetes" in tipo_consulta:
            resultados["vuelos"] = buscar_vuelos(datos)

        if "lugares" in tipo_consulta:
            resultados["lugares"] = buscar_lugares(datos)

        if "alojamientos" in tipo_consulta or "autos" in tipo_consulta:
            resultados["links"] = generar_links(datos)

        if "general" in tipo_consulta:
            resultados["general"] = True

    except Exception as e:
        print("Error en funciones:", e)
        return "Ups 😅 hubo un problema procesando tu consulta.", contexto
    try:
        prompt_sistema = """
                Sos un asistente de viajes amigable, claro y útil.
                Tu tarea es responder al usuario usando:
                - el historial de conversación
                - los datos obtenidos de APIs
                
                Estilo:
                - cercano y humano
                - usar emojis moderadamente
                - claro y directo
                - no inventar datos

                Reglas:
                - responder exactamente a lo que el usuario pidió
                - NO hacer preguntas innecesarias
                - NO invitar a seguir interactuando
                - NO despedirse automáticamente
                - ser útil pero conciso

                Comportamiento:
                - responder siempre de forma natural y completa
                - nunca cerrar la conversación por iniciativa propia
                - solo responder al contenido del mensaje actual

                Si hay resultados:
                - mostrarlos de forma ordenada

                Si no hay:
                - sugerir alternativas brevemente
        
                """
        mensajes = [{"role": "system", "content": prompt_sistema}]
        mensajes.extend(historial[-6:])  
        mensajes.append({
            "role": "user",
            "content": f"""
            Datos interpretados:
            {json.dumps(datos)}

            Resultados obtenidos:
            {json.dumps(resultados)}

            Generá una respuesta para el usuario.
            """})
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=mensajes,
            temperature=0.7
        )
        mensaje_final = respuesta.choices[0].message.content.strip()

    except Exception as e:
        print("Error generando respuesta IA:", e)
        mensaje_final = "Encontré info útil pero hubo un problema al armar la respuesta 😅"

    return mensaje_final, contexto