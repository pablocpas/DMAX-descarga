import time
import subprocess
import json
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# --- Configuración ---
BASE_URL = "https://dmax.marca.com/series/como-lo-hacen"

# ¡CAMBIA ESTOS VALORES SEGÚN EL EPISODIO QUE QUIERAS!
TARGET_SEASON_TEXT = "Temporada 13"
TARGET_EPISODE_TITLE = "Episodio 20" # Ejemplo, ajusta al episodio deseado

MPD_URL_IDENTIFIER = ".mpd"
WAIT_FOR_MPD_TIMEOUT = 45
SELENIUM_TIMEOUT = 25 # Aumentado ligeramente por si las esperas de placeholder toman tiempo

# --- Configuración del Driver Local (sin cambios) ---
def setup_driver_local():
    print("Configurando el driver LOCAL de Chrome con selenium-wire...")
    chrome_options_local = ChromeOptions()
    # chrome_options_local.add_argument("--headless=new")
    chrome_options_local.add_argument("--disable-gpu")
    chrome_options_local.add_argument("--no-sandbox")
    chrome_options_local.add_argument("--disable-dev-shm-usage")
    chrome_options_local.add_argument("--start-maximized")
    chrome_options_local.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36") # User agent actualizado

    sw_options = {'auto_config': True}
    try:
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options_local,
            seleniumwire_options=sw_options
        )
        driver.implicitly_wait(5)
        print("Driver LOCAL de Chrome con selenium-wire configurado.")
        if hasattr(driver, 'proxy') and driver.proxy:
             print(f"Selenium-wire proxy (local) iniciado en: {driver.proxy.host}:{driver.proxy.port}")
        return driver
    except Exception as e:
        print(f"Error configurando el driver LOCAL: {e}")
        if "cannot find Chrome binary" in str(e).lower():
            print("Asegúrate de que Google Chrome (o Chromium) está instalado y en el PATH.")
        elif "DevToolsActivePort" in str(e):
            print("Error 'DevToolsActivePort'. Chrome podría no haberse iniciado correctamente.")
        raise

# --- Funciones de Interacción con DMAX ---
def accept_cookies(driver):
    print("Intentando aceptar cookies si aparece el banner...")
    try:
        cookie_button_xpath = "//button[contains(text(), 'ACEPTAR TODO') or contains(text(), 'Aceptar y cerrar') or @id='onetrust-accept-btn-handler']"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))
        ).click()
        print("Banner de cookies aceptado.")
        time.sleep(2)
    except TimeoutException:
        print("No se encontró el banner de cookies o no se pudo hacer clic.")
    except Exception as e:
        print(f"Error al intentar aceptar cookies: {e}")


# Asumimos que BASE_URL, MPD_URL_IDENTIFIER, WAIT_FOR_MPD_TIMEOUT, SELENIUM_TIMEOUT
# TARGET_SEASON_TEXT, TARGET_EPISODE_TITLE están definidos globalmente.

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Asumimos que BASE_URL, MPD_URL_IDENTIFIER, WAIT_FOR_MPD_TIMEOUT, SELENIUM_TIMEOUT
# TARGET_SEASON_TEXT, TARGET_EPISODE_TITLE están definidos globalmente.

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Asumimos globales
# ...

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Asumimos globales: BASE_URL, MPD_URL_IDENTIFIER, WAIT_FOR_MPD_TIMEOUT, SELENIUM_TIMEOUT
# TARGET_SEASON_TEXT, TARGET_EPISODE_TITLE

def find_and_click_episode(driver, season_text, episode_title):
    print(f"Navegando a la página de la serie: {BASE_URL}")
    driver.get(BASE_URL)
    
    print("Intentando aceptar cookies...")
    try:
        cookie_button_xpath = "//button[contains(text(), 'ACEPTAR TODO') or contains(text(), 'Aceptar y cerrar') or @id='onetrust-accept-btn-handler']"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))).click()
        print("Banner de cookies aceptado."); time.sleep(2)
    except TimeoutException: print("No se encontró/clicó banner de cookies (Timeout).")
    except Exception as e_cookie: print(f"Error aceptando cookies: {e_cookie}")

    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)

    try:
        # 1. & 2. Selección de temporada
        print("Buscando el selector de temporada...")
        season_dropdown_trigger_xpath = "//div[contains(@class, 'select__value') and contains(., 'Temporada')]"
        s_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, season_dropdown_trigger_xpath)))
        print(f"Click en selector de temporada: '{s_trigger.text}'")
        driver.execute_script("arguments[0].click();", s_trigger)
        time.sleep(1.5)

        print(f"Buscando temporada '{season_text}'...")
        season_item_xpath = f"//div[contains(@class, 'select__option') and starts-with(normalize-space(.), '{season_text}')]"
        s_item = wait.until(EC.element_to_be_clickable((By.XPATH, season_item_xpath)))
        print(f"Click en temporada: '{s_item.text.strip()}'")
        driver.execute_script("arguments[0].click();", s_item)
        
        print(f"Temporada '{season_text}' seleccionada. Pausando para carga de episodios..."); time.sleep(10)

        # 3. Localizar la TARJETA que contiene la imagen con aria-label
        card_container_xpath = f"//div[contains(@class, 'card--video')][.//img[@aria-label='{episode_title}']]"
        print(f"Buscando contenedor de la tarjeta del episodio con XPath: {card_container_xpath}")
        
        card_container_element = None 
        try:
            card_container_element = wait.until(EC.presence_of_element_located((By.XPATH, card_container_xpath)))
            print(f"Contenedor de tarjeta encontrado: {card_container_element.tag_name}.{card_container_element.get_attribute('class')}")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", card_container_element)
            time.sleep(1)
            wait.until(EC.visibility_of(card_container_element))
            print("Contenedor de tarjeta ahora visible.")
        except TimeoutException:
            print(f"Timeout: No se encontró/visible el contenedor de la tarjeta del episodio '{episode_title}'."); return None

        # Localizar el botón de play (placeholder) DENTRO de la tarjeta
        play_button_placeholder_xpath_relative = ".//div[contains(@class, 'card__placeholder')]"
        print(f"Buscando botón de play (placeholder) con XPath relativo: {play_button_placeholder_xpath_relative}")
        
        play_button_element = None
        try:
            play_button_element = WebDriverWait(card_container_element, 5).until(
                EC.element_to_be_clickable((By.XPATH, play_button_placeholder_xpath_relative))
            )
            print(f"Botón de play encontrado y clickeable: {play_button_element.tag_name}.{play_button_element.get_attribute('class')}")
        except Exception as e_play_btn:
            print(f"Advertencia: Botón de play (placeholder) no encontrado o no clickeable en 5s: {e_play_btn}")
            # Si no se encuentra el botón de play explícito, podríamos intentar clickear la tarjeta contenedora.
            # Pero dado que el clic JS en el botón de play funcionó, nos enfocaremos en eso.
            # Si play_button_element es None, el script fallará más adelante, lo cual está bien.

        # Neutralizar ancestro 'grid__content' si intercepta el centro de la tarjeta contenedora
        print("Verificando si un ancestro ('grid__content') intercepta el centro de la tarjeta...")
        rect = card_container_element.rect
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2
        
        element_at_center_initial_js = driver.execute_script(
            "return document.elementFromPoint(arguments[0], arguments[1]);", center_x, center_y)

        if element_at_center_initial_js:
            initial_center_class = driver.execute_script("return arguments[0].className", element_at_center_initial_js)
            if "grid__content" in initial_center_class:
                print("  Interceptor 'grid__content' detectado. Intentando neutralizarlo...")
                try:
                    driver.execute_script("arguments[0].style.pointerEvents = 'none';", element_at_center_initial_js)
                    print("    'grid__content' cambiado a pointer-events: none.")
                    time.sleep(0.5) 
                except Exception as e_neutralize_grid:
                    print(f"    Error neutralizando 'grid__content': {e_neutralize_grid}")
        
        if hasattr(driver, 'requests'): del driver.requests
        else: print("ADVERTENCIA: 'requests' no en driver."); return None

        # Intento de clic en el BOTÓN DE PLAY (si se encontró)
        if not play_button_element:
            print("ERROR CRÍTICO: No se pudo localizar el botón de play. Abortando clic.")
            return None
            
        print(f"Intentando clic en el BOTÓN DE PLAY (placeholder) '{play_button_element.tag_name}.{play_button_element.get_attribute('class')}'")
        try:
            # El clic Selenium falló por intercepción del 'grid.grid--video', así que vamos directo al JS
            print("  Usando clic JavaScript en el botón de play...")
            driver.execute_script("arguments[0].click();", play_button_element)
            print("  Clic (JavaScript) en botón de play supuestamente realizado.")
        except Exception as e_click_play_js:
            print(f"  Error en clic JavaScript en botón de play: {e_click_play_js}")
            print("  Intentando clic JS en la tarjeta contenedora como último recurso...")
            try:
                driver.execute_script("arguments[0].click();", card_container_element)
                print("  Clic (JavaScript) en tarjeta contenedora (último recurso) supuestamente realizado.")
            except Exception as e_click_card_js_last_resort:
                print(f"  Error en clic JavaScript en tarjeta (último recurso): {e_click_card_js_last_resort}")
                return None # Si todo falla

        time.sleep(2) # Pausa post-clic

        # 4. Esperar MPD
        print(f"Episodio clicado. Esperando MPD ({WAIT_FOR_MPD_TIMEOUT}s)...")
        start_time = time.time()
        while time.time() - start_time < WAIT_FOR_MPD_TIMEOUT:
            if not hasattr(driver, 'requests'): print("ERROR CRÍTICO: 'requests' no en driver."); return None
            for r in driver.requests:
                if MPD_URL_IDENTIFIER in r.url and r.response and 200 <= r.response.status_code < 300:
                    print(f"¡MPD encontrado!: {r.url}"); return r.url
            time.sleep(0.5)
        
        print("No se encontró MPD.")
        if hasattr(driver, 'requests') and driver.requests:
            print("Últimas solicitudes capturadas:")
            relevant_requests = [req for req in driver.requests[-10:] if MPD_URL_IDENTIFIER in req.url or ".m3u8" in req.url] or driver.requests[-10:]
            for req_f in relevant_requests: print(f" - {req_f.method} {req_f.url} (Status: {req_f.response.status_code if req_f.response else 'N/A'})")
        return None

    except TimeoutException as e: print(f"Timeout general: {e.msg if hasattr(e, 'msg') else e}"); return None
    except NoSuchElementException as e: print(f"Elemento no encontrado (general): {e.msg if hasattr(e, 'msg') else e}"); return None
    except Exception as e:
        print(f"Error inesperado en find_and_click_episode: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    
# --- Función de Descarga con yt-dlp (sin cambios) ---
def download_video_with_yt_dlp(mpd_url, output_filename="video_descargado.mp4"):
    if not mpd_url:
        print("No se proporcionó URL del MPD. No se puede descargar.")
        return False
    print(f"Intentando descargar desde: {mpd_url}")
    try:
        command = [
            'yt-dlp', mpd_url,
            '-o', output_filename,
            '--allow-unplayable-formats', '--quiet', '--progress',
            '--referer', BASE_URL
        ]
        print(f"Ejecutando comando yt-dlp: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(f"\n¡Descarga completada! Vídeo guardado como: {output_filename}")
            return True
        else:
            print("\nError durante la descarga con yt-dlp.")
            print(f"Código de retorno: {process.returncode}")
            if stdout: print(f"Stdout de yt-dlp:\n{stdout.decode(errors='ignore')}")
            if stderr: print(f"Stderr de yt-dlp:\n{stderr.decode(errors='ignore')}")
            return False
    except FileNotFoundError:
        print("Error: 'yt-dlp' no encontrado. Asegúrate de que esté instalado y en el PATH.")
        return False
    except Exception as e:
        print(f"Excepción al usar yt-dlp: {e}")
        return False

# --- Bloque Principal de Ejecución (sin cambios) ---
if __name__ == "__main__":
    driver = None
    try:
        driver = setup_driver_local()
        if driver:
            print(f"--- Iniciando proceso para DMAX: {TARGET_SEASON_TEXT} - {TARGET_EPISODE_TITLE} ---")
            current_mpd_url = find_and_click_episode(driver, TARGET_SEASON_TEXT, TARGET_EPISODE_TITLE)
            if current_mpd_url:
                print(f"URL del MPD obtenida: {current_mpd_url}")
                s_slug = TARGET_SEASON_TEXT.lower().replace(" ", "-").replace(":", "")
                e_slug = TARGET_EPISODE_TITLE.lower().replace(" ", "-").replace(":", "")
                file_name = f"dmax_como-lo-hacen_{s_slug}_{e_slug}.mp4"
                print(f"Nombre de archivo: {file_name}")
                download_video_with_yt_dlp(current_mpd_url, file_name)
            else:
                print("No se pudo obtener la URL del MPD. Abortando descarga.")
        else:
            print("Fallo al inicializar el driver. Abortando.")
    except Exception as e:
        print(f"Error principal no capturado: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Cerrando navegador...")
            driver.quit()
        print("--- Proceso finalizado ---")
