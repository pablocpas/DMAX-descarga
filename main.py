import time
import subprocess
import json
import os # Para crear carpetas
import re # Para extraer números de temporada/episodio
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# --- Configuración General ---
# ¡CAMBIA ESTOS VALORES!
SERIES_SLUG = "como-lo-hacen"  # El slug de la URL de la serie (ej. "control-de-carreteras")
TARGET_SEASON_INPUT = "13"      # Puede ser "Temporada 13" o solo el número "13"
TARGET_EPISODE_INPUT = "20"     # Puede ser "Episodio 20" o solo el número "20" (si DOWNLOAD_MODE es "single")
DOWNLOAD_MODE = "single"       # Opciones: "single", "season"
                                # "all" (para todas las temporadas) se podría implementar después

# Si usas números para TARGET_EPISODE_INPUT, este prefijo se añadirá.
# Si el título del episodio en la web es solo "20", deja esto vacío "".
# Si es "Episodio 20", usa "Episodio ".
EPISODE_NUMBER_PREFIX = "Episodio "
OUTPUT_BASE_DIR = "DMAX_Descargas" # Carpeta base para las descargas

# --- Configuraciones Técnicas ---
MPD_URL_IDENTIFIER = ".mpd"
WAIT_FOR_MPD_TIMEOUT = 45
SELENIUM_TIMEOUT = 25
MAX_RETRIES_MPD = 1 # Cuántas veces reintentar obtener el MPD para un episodio antes de saltarlo

# --- Funciones de Utilidad ---
def sanitize_filename(name):
    """Limpia un nombre para usarlo como archivo/carpeta."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name) # Caracteres inválidos en Windows/Linux
    name = name.replace(" ", "-").lower()
    return name

def build_series_url(slug):
    return f"https://dmax.marca.com/series/{slug}"

# --- Configuración del Driver ---
def setup_driver_local():
    print("Configurando el driver LOCAL de Chrome con selenium-wire...")
    chrome_options_local = ChromeOptions()
    # chrome_options_local.add_argument("--headless=new")
    chrome_options_local.add_argument("--disable-gpu")
    chrome_options_local.add_argument("--no-sandbox")
    chrome_options_local.add_argument("--disable-dev-shm-usage")
    chrome_options_local.add_argument("--start-maximized")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    chrome_options_local.add_argument(f"user-agent={ua}")
    sw_options = {'auto_config': True, 'disable_capture': False} # Asegurar captura
    try:
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options_local,
            seleniumwire_options=sw_options
        )
        driver.implicitly_wait(5)
        print("Driver LOCAL de Chrome con selenium-wire configurado.")
        return driver
    except Exception as e:
        print(f"Error configurando el driver LOCAL: {e}"); raise

# --- Funciones de Interacción con DMAX ---
def accept_cookies(driver):
    print("Intentando aceptar cookies...")
    try:
        cookie_button_xpath = "//button[contains(text(), 'ACEPTAR TODO') or contains(text(), 'Aceptar y cerrar') or @id='onetrust-accept-btn-handler']"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))).click()
        print("Banner de cookies aceptado."); time.sleep(2)
    except: print("No se encontró/clicó banner de cookies o ya fue aceptado.")

def select_season(driver, season_input_text):
    """Selecciona la temporada deseada. season_input_text puede ser 'Temporada X' o 'X'."""
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
    print(f"Intentando seleccionar la temporada '{season_input_text}'...")

    # Normalizar season_input_text para que empiece con "Temporada " si es solo un número
    if season_input_text.isdigit():
        target_season_text_normalized = f"Temporada {season_input_text}"
    else:
        target_season_text_normalized = season_input_text
    
    print(f"  Texto de temporada normalizado para búsqueda: '{target_season_text_normalized}'")

    try:
        print("  Buscando el selector de temporada...")
        season_dropdown_trigger_xpath = "//div[contains(@class, 'select__value') and contains(., 'Temporada')]"
        s_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, season_dropdown_trigger_xpath)))
        print(f"  Click en selector de temporada actual: '{s_trigger.text}'")
        driver.execute_script("arguments[0].click();", s_trigger)
        time.sleep(1.5)

        print(f"  Buscando item de temporada '{target_season_text_normalized}' en el desplegable...")
        # Usamos starts-with para permitir "Temporada X (Y episodios)"
        season_item_xpath = f"//div[contains(@class, 'select__option') and starts-with(normalize-space(.), '{target_season_text_normalized}')]"
        s_item = wait.until(EC.element_to_be_clickable((By.XPATH, season_item_xpath)))
        actual_season_text_on_page = s_item.text.strip()
        print(f"  Click en temporada encontrada: '{actual_season_text_on_page}'")
        driver.execute_script("arguments[0].click();", s_item)
        
        print(f"  Temporada '{actual_season_text_on_page}' seleccionada. Pausando para carga de episodios..."); time.sleep(8) # Más tiempo
        return actual_season_text_on_page # Devolver el texto real de la temporada seleccionada
    except Exception as e:
        print(f"  ERROR al seleccionar la temporada '{target_season_text_normalized}': {e}")
        # driver.save_screenshot(f"error_selecting_season_{sanitize_filename(target_season_text_normalized)}.png")
        return None

def get_episode_elements_for_current_season(driver):
    """Devuelve una lista de WebElements para las tarjetas de episodio de la temporada actual."""
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
    print("Obteniendo lista de episodios para la temporada actual...")
    # XPath para todas las tarjetas de episodio visibles
    # Asumimos que cada tarjeta clickeable es un div.card.card--video que contiene una img con aria-label
    episode_cards_xpath = "//div[contains(@class, 'card--video')][.//img[@aria-label]]"
    try:
        # Esperar a que al menos una tarjeta esté presente y visible
        wait.until(EC.visibility_of_element_located((By.XPATH, episode_cards_xpath)))
        episode_elements = driver.find_elements(By.XPATH, episode_cards_xpath)
        if episode_elements:
            print(f"  Encontrados {len(episode_elements)} elementos de episodio.")
            return episode_elements
        else:
            print("  No se encontraron elementos de episodio para la temporada actual.")
            return []
    except TimeoutException:
        print("  Timeout: No se encontraron tarjetas de episodio visibles para la temporada actual.")
        return []
    except Exception as e:
        print(f"  Error obteniendo elementos de episodio: {e}")
        return []

def click_episode_and_get_mpd(driver, episode_element_to_click, episode_title_for_log=""):
    """
    Realiza el clic en un WebElement de episodio (tarjeta o botón de play) y busca el MPD.
    episode_element_to_click: El WebElement que se considera el objetivo principal del clic.
    """
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
    mpd_url = None
    
    log_prefix = f"Episodio '{episode_title_for_log}': " if episode_title_for_log else ""

    try:
        print(f"{log_prefix}Asegurando visibilidad y preparando para clic...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", episode_element_to_click)
        time.sleep(0.5)
        wait.until(EC.visibility_of(episode_element_to_click))

        # Intentar localizar el botón de play (placeholder) DENTRO del episode_element_to_click
        play_button_xpath_relative = ".//div[contains(@class, 'card__placeholder')]"
        play_button_element = None
        try:
            play_button_element = WebDriverWait(episode_element_to_click, 3).until( # Corto timeout
                EC.element_to_be_clickable((By.XPATH, play_button_xpath_relative))
            )
            print(f"{log_prefix}Botón de play interno encontrado. Se priorizará este.")
            element_for_final_click = play_button_element
        except:
            print(f"{log_prefix}No se encontró botón de play interno o no es clickeable. Se usará la tarjeta/elemento principal.")
            element_for_final_click = episode_element_to_click
        
        # Neutralizar ancestro 'grid__content' si intercepta el centro del elemento a clickear
        print(f"{log_prefix}Verificando ancestro 'grid__content'...")
        rect = element_for_final_click.rect # Usar el elemento que vamos a clickear para el centro
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2
        
        element_at_center_js = driver.execute_script(
            "return document.elementFromPoint(arguments[0], arguments[1]);", center_x, center_y)

        if element_at_center_js:
            center_class = driver.execute_script("return arguments[0].className", element_at_center_js)
            if "grid__content" in center_class:
                print(f"{log_prefix}  Interceptor 'grid__content' detectado. Neutralizando...")
                try:
                    driver.execute_script("arguments[0].style.pointerEvents = 'none';", element_at_center_js)
                    print(f"{log_prefix}    'grid__content' cambiado a pointer-events: none.")
                    time.sleep(0.3) 
                except Exception as e_neut: print(f"{log_prefix}    Error neutralizando: {e_neut}")
        
        # Limpiar requests y click
        if hasattr(driver, 'requests'): del driver.requests
        else: print(f"{log_prefix}ADVERTENCIA: 'requests' no en driver."); return None

        print(f"{log_prefix}Intentando clic JS en: {element_for_final_click.tag_name}.{element_for_final_click.get_attribute('class')}")
        driver.execute_script("arguments[0].click();", element_for_final_click)
        print(f"{log_prefix}Clic JS supuestamente realizado.")
        time.sleep(2) # Pausa post-clic

        # Esperar MPD
        print(f"{log_prefix}Esperando MPD ({WAIT_FOR_MPD_TIMEOUT}s)...")
        start_time = time.time()
        while time.time() - start_time < WAIT_FOR_MPD_TIMEOUT:
            if not hasattr(driver, 'requests'): print(f"{log_prefix}ERROR CRÍTICO: 'requests' no en driver."); return None
            for r in driver.requests:
                if MPD_URL_IDENTIFIER in r.url and r.response and 200 <= r.response.status_code < 300:
                    mpd_url = r.url
                    print(f"{log_prefix}¡MPD encontrado!: {mpd_url}"); return mpd_url
            time.sleep(0.5)
        
        print(f"{log_prefix}No se encontró MPD para este episodio.")
        return None

    except Exception as e:
        print(f"{log_prefix}Error durante el proceso de clic y obtención de MPD: {e}")
        # driver.save_screenshot(f"error_click_mpd_{sanitize_filename(episode_title_for_log)}.png")
        return None


# --- Función de Descarga ---
def download_video_with_yt_dlp(mpd_url, output_path, series_url_for_referer):
    if not mpd_url: print("No se proporcionó URL del MPD."); return False
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Intentando descargar desde: {mpd_url}")
    print(f"Guardando en: {output_path}")
    try:
        command = [
            'yt-dlp', mpd_url,
            '-o', output_path,
            '--allow-unplayable-formats', '--quiet', '--progress',
            '--referer', series_url_for_referer, # Usar la URL de la serie como referer
            # '--no-warnings', # Para suprimir algunos warnings comunes de yt-dlp
            # '--retries', '5', # Reintentos en caso de problemas de red
            # '--fragment-retries', '5' 
        ]
        print(f"Ejecutando comando yt-dlp: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(f"¡Descarga completada! Vídeo guardado como: {output_path}\n")
            return True
        else:
            print(f"\nError durante la descarga con yt-dlp para {os.path.basename(output_path)}.")
            print(f"  Código de retorno: {process.returncode}")
            if stdout: print(f"  Stdout de yt-dlp:\n{stdout.decode(errors='ignore')}")
            if stderr: print(f"  Stderr de yt-dlp:\n{stderr.decode(errors='ignore')}")
            return False
    except FileNotFoundError: print("Error: 'yt-dlp' no encontrado."); return False
    except Exception as e: print(f"Excepción al usar yt-dlp: {e}"); return False

# --- Lógica Principal ---
def main():
    base_series_url = build_series_url(SERIES_SLUG)
    print(f"--- Iniciando proceso para DMAX ---")
    print(f"Serie: {SERIES_SLUG} (URL: {base_series_url})")
    print(f"Modo de descarga: {DOWNLOAD_MODE}")

    driver = None
    try:
        driver = setup_driver_local()
        driver.get(base_series_url) # Ir a la página principal de la serie
        accept_cookies(driver)

        selected_season_text_on_page = select_season(driver, TARGET_SEASON_INPUT)
        if not selected_season_text_on_page:
            print(f"No se pudo seleccionar la temporada '{TARGET_SEASON_INPUT}'. Abortando.")
            return

        # Preparar la carpeta de salida para la serie y temporada
        series_folder_name = sanitize_filename(SERIES_SLUG)
        season_folder_name = sanitize_filename(selected_season_text_on_page)
        season_output_dir = os.path.join(OUTPUT_BASE_DIR, series_folder_name, season_folder_name)

        if DOWNLOAD_MODE == "single":
            print(f"Modo 'single': Buscando episodio '{TARGET_EPISODE_INPUT}'")
            
            # Normalizar el título del episodio si es solo un número
            target_episode_title_normalized = TARGET_EPISODE_INPUT
            if TARGET_EPISODE_INPUT.isdigit() and EPISODE_NUMBER_PREFIX:
                target_episode_title_normalized = f"{EPISODE_NUMBER_PREFIX}{TARGET_EPISODE_INPUT}"
            
            print(f"  Título de episodio normalizado para búsqueda: '{target_episode_title_normalized}'")

            # XPath para la tarjeta específica del episodio por aria-label en la imagen
            episode_card_xpath = f"//div[contains(@class, 'card--video')][.//img[@aria-label='{target_episode_title_normalized}']]"
            try:
                episode_card_element = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, episode_card_xpath))
                )
                print(f"  Tarjeta del episodio '{target_episode_title_normalized}' encontrada.")

                mpd_url = None
                for attempt in range(MAX_RETRIES_MPD + 1):
                    print(f"  Intento {attempt + 1}/{MAX_RETRIES_MPD + 1} para obtener MPD...")
                    # Borrar requests antes de intentar obtener MPD para este episodio
                    if hasattr(driver, 'requests'): del driver.requests
                    
                    mpd_url = click_episode_and_get_mpd(driver, episode_card_element, target_episode_title_normalized)
                    if mpd_url: break
                    if attempt < MAX_RETRIES_MPD:
                        print(f"  Fallo al obtener MPD. Reintentando en 5 segundos...")
                        time.sleep(5)
                        # Podríamos intentar recargar la lista o la página aquí si fuera necesario
                
                if mpd_url:
                    file_name_base = sanitize_filename(target_episode_title_normalized)
                    output_file_path = os.path.join(season_output_dir, f"{file_name_base}.mp4")
                    download_video_with_yt_dlp(mpd_url, output_file_path, base_series_url)
                else:
                    print(f"  No se pudo obtener la URL del MPD para '{target_episode_title_normalized}' después de reintentos.")

            except TimeoutException:
                print(f"  Timeout: No se encontró la tarjeta del episodio '{target_episode_title_normalized}'.")
            except Exception as e:
                print(f"  Error procesando episodio '{target_episode_title_normalized}': {e}")


        elif DOWNLOAD_MODE == "season":
            print(f"Modo 'season': Descargando todos los episodios de '{selected_season_text_on_page}'")
            episode_elements = get_episode_elements_for_current_season(driver)
            
            if not episode_elements:
                print(f"No se encontraron episodios para la temporada '{selected_season_text_on_page}'. Abortando.")
                return

            total_episodes = len(episode_elements)
            print(f"Se intentarán descargar {total_episodes} episodios.")

            for i, episode_card_element in enumerate(episode_elements):
                # Obtener el título del episodio desde el aria-label de la imagen DENTRO de la tarjeta
                episode_title_from_page = "Desconocido"
                try {
                    img_element = WebDriverWait(episode_card_element, 5).until(
                        EC.presence_of_element_located((By.XPATH, ".//img[@aria-label]"))
                    )
                    episode_title_from_page = img_element.get_attribute("aria-label").strip()
                } except:
                    # Fallback: intentar obtener de h2.card__title
                    try:
                        title_h2_element = WebDriverWait(episode_card_element, 2).until(
                            EC.presence_of_element_located((By.XPATH, ".//h2[contains(@class, 'card__title')]"))
                        )
                        episode_title_from_page = title_h2_element.text.strip()
                    except:
                        print(f"  Advertencia: No se pudo obtener el título para el episodio {i+1}.")
                        episode_title_from_page = f"episodio_desconocido_{i+1}"
                
                print(f"\n--- Procesando episodio {i+1}/{total_episodes}: '{episode_title_from_page}' ---")

                mpd_url = None
                for attempt in range(MAX_RETRIES_MPD + 1):
                    print(f"  Intento {attempt + 1}/{MAX_RETRIES_MPD + 1} para obtener MPD...")
                    # Borrar requests antes de intentar obtener MPD para este episodio
                    if hasattr(driver, 'requests'): del driver.requests

                    mpd_url = click_episode_and_get_mpd(driver, episode_card_element, episode_title_from_page)
                    if mpd_url: break
                    if attempt < MAX_RETRIES_MPD:
                        print(f"  Fallo al obtener MPD. Reintentando en 5 segundos...")
                        time.sleep(5)
                        # Podríamos considerar recargar la sección de episodios o hacer clic de nuevo en la temporada
                        # si los clics fallan consistentemente después del primero.
                        # Por ahora, solo reintentamos el clic en el mismo elemento.
                
                if mpd_url:
                    file_name_base = sanitize_filename(episode_title_from_page)
                    output_file_path = os.path.join(season_output_dir, f"{file_name_base}.mp4")
                    download_video_with_yt_dlp(mpd_url, output_file_path, base_series_url)
                else:
                    print(f"  No se pudo obtener la URL del MPD para '{episode_title_from_page}' después de reintentos. Saltando.")
                
                # Pequeña pausa entre episodios para no sobrecargar
                time.sleep(3) 
        else:
            print(f"Modo de descarga '{DOWNLOAD_MODE}' no reconocido.")

    except Exception as e:
        print(f"Error principal no capturado en el script: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Cerrando navegador...")
            driver.quit()
        print("--- Proceso finalizado ---")

if __name__ == "__main__":
    main()
