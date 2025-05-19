import time
import subprocess
import json
import os
import re
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# --- Configuraciones Técnicas (pueden quedarse como globales o moverse a un config si crece) ---
MPD_URL_IDENTIFIER = ".mpd"
WAIT_FOR_MPD_TIMEOUT = 45
SELENIUM_TIMEOUT = 30 # Un poco más de margen para interacciones
MAX_RETRIES_MPD = 1
EPISODE_NUMBER_PREFIX = "Episodio " # Ajusta si los títulos son solo números
OUTPUT_BASE_DIR = "DMAX_Descargas"

# --- Funciones de Utilidad ---
def sanitize_filename(name):
    name = str(name) # Asegurarse que es string
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.replace(" ", "-").lower()
    # Evitar nombres de archivo excesivamente largos
    return name[:150]

def build_series_url_from_slug(slug):
    return f"https://dmax.marca.com/series/{slug}"

# --- Configuración del Driver ---
def setup_driver_local():
    print("Configurando el driver LOCAL de Chrome con selenium-wire...")
    chrome_options_local = ChromeOptions()
    # Descomenta para headless:
    # chrome_options_local.add_argument("--headless=new")
    # Optimizaciones comunes para headless/servidores:
    chrome_options_local.add_argument("--disable-gpu")
    chrome_options_local.add_argument("--no-sandbox") # Necesario en Linux/WSL/Docker
    chrome_options_local.add_argument("--disable-dev-shm-usage") # Crítico en Linux/WSL/Docker
    chrome_options_local.add_argument("--window-size=1920,1080") # Tamaño de ventana para headless
    # chrome_options_local.add_argument("--start-maximized") # Para no-headless
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    chrome_options_local.add_argument(f"user-agent={ua}")
    
    sw_options = {
        'auto_config': True, 
        'disable_capture': False # Asegurar que la captura de red esté habilitada
    }
    try:
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options_local,
            seleniumwire_options=sw_options
        )
        driver.implicitly_wait(5) # Espera implícita general
        print("Driver LOCAL de Chrome con selenium-wire configurado.")
        return driver
    except Exception as e:
        print(f"Error configurando el driver LOCAL: {e}")
        if "cannot find chrome binary" in str(e).lower():
            print("Asegúrate de que Google Chrome (o Chromium) está instalado y en el PATH.")
        raise

# --- Funciones de Interacción con DMAX ---
def accept_cookies(driver):
    print("Intentando aceptar cookies...")
    try:
        cookie_button_xpath = "//button[contains(text(), 'ACEPTAR TODO') or contains(text(), 'Aceptar y cerrar') or @id='onetrust-accept-btn-handler']"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))).click()
        print("Banner de cookies aceptado."); time.sleep(2)
    except TimeoutException: print("No se encontró banner de cookies (Timeout) o ya fue aceptado.")
    except Exception as e_cookie: print(f"Error aceptando cookies: {e_cookie}")

def get_all_series(driver):
    series_page_url = "https://dmax.marca.com/series"
    print(f"\nObteniendo lista de todas las series desde: {series_page_url}...")
    driver.get(series_page_url)
    # La aceptación de cookies puede ser necesaria aquí si el banner cubre los scripts JSON-LD
    accept_cookies(driver) # Descomentar si es necesario, aunque ya se llama en main
    
    WebDriverWait(driver, SELENIUM_TIMEOUT).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    time.sleep(2) # Pausa adicional para que carguen los scripts JSON-LD

    series_data = {}
    try:
        json_ld_scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        if not json_ld_scripts:
            print("  No se encontraron scripts JSON-LD para la lista de series inicial.")
        
        for script_tag in json_ld_scripts:
            try:
                json_content = json.loads(script_tag.get_attribute('innerHTML'))
                if json_content.get("@type") == "ItemList" and "itemListElement" in json_content:
                    for item_entry in json_content["itemListElement"]:
                        item_details = item_entry.get("item", {})
                        if item_details.get("@type") == "Webpage":
                            series_name = item_details.get("name", "").strip()
                            series_url = item_details.get("url", "")
                            if series_name and series_url and "/series/" in series_url:
                                slug = series_url.split('/series/')[-1].split('/')[0].split('?')[0]
                                if slug: series_data[series_name] = slug
            except: continue # Ignorar errores de parseo de JSON individuales

        # Fallback si JSON-LD no dio resultados o para complementar
        print("  Buscando series en estructura HTML de categoría (fallback/complemento)...")
        category_links = driver.find_elements(By.XPATH, "//li[contains(@class, 'category-link__letter__list__item')]/a[@class='link']")
        for link_el in category_links:
            series_name = link_el.text.strip()
            series_url = link_el.get_attribute('href')
            if series_name and series_url and "/series/" in series_url:
                slug = series_url.split('/series/')[-1].split('/')[0].split('?')[0]
                if slug and series_name not in series_data: # Añadir si no está ya
                    series_data[series_name] = slug
        
        if series_data: print(f"  Se encontraron {len(series_data)} series en total.")
        else: print("  No se pudo extraer ninguna serie.")
            
    except Exception as e: print(f"Error obteniendo la lista de series: {e}")
    return dict(sorted(series_data.items()))


def select_season_interactive(driver, current_series_url):
    print(f"\n--- Selección de Temporada para {current_series_url.split('/')[-1]} ---")
    driver.get(current_series_url) 
    # accept_cookies(driver) # Ya debería estar aceptado, pero por si acaso
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)

    try:
        print("  Abriendo selector de temporadas...")
        s_trigger_xpath = "//div[contains(@class, 'select__value') and contains(., 'Temporada')]"
        s_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, s_trigger_xpath)))
        default_season_text = s_trigger.text.strip()
        driver.execute_script("arguments[0].click();", s_trigger)
        time.sleep(1.5)

        s_options_xpath = "//div[contains(@class, 'select__option')]"
        s_elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, s_options_xpath)))
        
        available_s_texts = [el.text.strip() for el in s_elements if el.text.strip()]
        if not available_s_texts:
            print(f"  No se encontraron opciones de temporada. Usando por defecto: '{default_season_text}'")
            if "Temporada" in default_season_text: return default_season_text
            return None

        print("  Temporadas disponibles:")
        for i, s_text in enumerate(available_s_texts): print(f"    {i+1}. {s_text}")
        
        while True:
            choice = input(f"  Elige temporada (1-{len(available_s_texts)}), o 'q' para salir: ")
            if choice.lower() == 'q': 
                try: driver.execute_script("arguments[0].click();", s_trigger) # Cerrar desplegable
                except: pass
                return None
            try:
                num = int(choice)
                if 1 <= num <= len(available_s_texts):
                    selected_s_text = available_s_texts[num-1]
                    print(f"  Seleccionando '{selected_s_text}'...")
                    driver.execute_script("arguments[0].click();", s_elements[num-1])
                    time.sleep(8); return selected_s_text
                else: print("  Número fuera de rango.")
            except ValueError: print("  Entrada inválida.")
    except Exception as e: print(f"  Error obteniendo/seleccionando temporadas: {e}"); return None

def get_episode_elements_for_current_season(driver):
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
    print("  Obteniendo lista de episodios para la temporada actual...")
    ep_cards_xpath = "//div[contains(@class, 'card--video')][.//img[@aria-label]]"
    try:
        wait.until(EC.visibility_of_element_located((By.XPATH, ep_cards_xpath)))
        ep_elements = driver.find_elements(By.XPATH, ep_cards_xpath)
        print(f"    Encontrados {len(ep_elements)} elementos de episodio.")
        return ep_elements
    except: print("    No se encontraron tarjetas de episodio."); return []

def click_episode_and_get_mpd(driver, episode_card_element, episode_title_for_log=""):
    wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
    log_prefix = f"Episodio '{episode_title_for_log}': " if episode_title_for_log else ""
    try:
        print(f"{log_prefix}Asegurando visibilidad y preparando para clic...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", episode_card_element)
        time.sleep(0.5); wait.until(EC.visibility_of(episode_card_element))

        play_button_xpath = ".//div[contains(@class, 'card__placeholder')]"
        element_for_final_click = episode_card_element # Por defecto
        try:
            play_button = WebDriverWait(episode_card_element, 3).until(EC.element_to_be_clickable((By.XPATH, play_button_xpath)))
            print(f"{log_prefix}Botón de play interno encontrado. Se usará este."); element_for_final_click = play_button
        except: print(f"{log_prefix}No se usará botón de play interno (no encontrado/clickeable). Se usará la tarjeta.")

        rect = element_for_final_click.rect
        center_x, center_y = rect['x'] + rect['width']/2, rect['y'] + rect['height']/2
        
        elem_at_center_js = driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", center_x, center_y)
        if elem_at_center_js:
            center_class = driver.execute_script("return arguments[0].className", elem_at_center_js)
            if "grid__content" in center_class and elem_at_center_js != element_for_final_click: # Asegurarse que no es el mismo
                print(f"{log_prefix}  Interceptor 'grid__content' detectado. Neutralizando...")
                try:
                    driver.execute_script("arguments[0].style.pointerEvents = 'none';", elem_at_center_js)
                    print(f"{log_prefix}    'grid__content' cambiado a pointer-events: none."); time.sleep(0.3)
                except Exception as e_neut: print(f"{log_prefix}    Error neutralizando: {e_neut}")
        
        if hasattr(driver, 'requests'): del driver.requests
        else: print(f"{log_prefix}ADVERTENCIA: 'requests' no en driver."); return None

        print(f"{log_prefix}Intentando clic JS en: {element_for_final_click.tag_name}.{element_for_final_click.get_attribute('class')}")
        driver.execute_script("arguments[0].click();", element_for_final_click)
        print(f"{log_prefix}Clic JS supuestamente realizado."); time.sleep(2)

        print(f"{log_prefix}Esperando MPD ({WAIT_FOR_MPD_TIMEOUT}s)...")
        start_time = time.time()
        for _ in range(int(WAIT_FOR_MPD_TIMEOUT / 0.5)): # Bucle con timeout
            if hasattr(driver, 'requests'):
                for r in driver.requests:
                    if MPD_URL_IDENTIFIER in r.url and r.response and 200 <= r.response.status_code < 300:
                        print(f"{log_prefix}¡MPD encontrado!: {r.url}"); return r.url
            time.sleep(0.5)
        print(f"{log_prefix}No se encontró MPD."); return None
    except Exception as e: print(f"{log_prefix}Error en clic/MPD: {e}"); return None

# --- Descarga ---
def download_video_with_yt_dlp(mpd_url, output_path, series_url_for_referer):
    if not mpd_url: print("No MPD URL."); return False
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Descargando: {mpd_url}\n  a: {output_path}")
    try:
        command = ['yt-dlp', mpd_url, '-o', output_path, '--allow-unplayable-formats', 
                   '--quiet', '--progress', '--referer', series_url_for_referer]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0: print(f"Descarga completa: {output_path}\n"); return True
        else: print(f"Error yt-dlp (code {process.returncode}):\n{stderr.decode(errors='ignore')[:500]}"); return False
    except Exception as e: print(f"Excepción yt-dlp: {e}"); return False

# --- Interfaz de Usuario y Lógica Principal ---
def prompt_for_series(available_series_map):
    if not available_series_map: print("No hay series disponibles."); return None
    print("\n--- Selección de Serie ---")
    while True:
        search = input("Buscar serie (o vacío para listar, 'q' salir): ").lower()
        if search == 'q': return None
        matches = {n: s for n, s in available_series_map.items() if search in n.lower()}
        if not matches: print("No hay coincidencias."); continue
        
        s_matches = sorted(matches.items())
        for i, (name, _) in enumerate(s_matches): print(f"  {i+1}. {name}")
        
        while True:
            choice = input(f"Elige serie (1-{len(s_matches)}), 'b' buscar, 'q' salir: ").lower()
            if choice == 'q': return None
            if choice == 'b': break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(s_matches):
                    print(f"Serie seleccionada: {s_matches[idx][0]}")
                    return s_matches[idx][1] # Devuelve el slug
                else: print("Número fuera de rango.")
            except ValueError: print("Entrada inválida.")
        if choice == 'b': continue
    return None # No debería llegar

def prompt_for_download_mode_and_episode(driver, selected_season_text, current_episode_elements):
    print("\n--- Modo de Descarga ---")
    while True:
        mode = input(f"Elige: (1) Episodio único, (2) Temporada completa ('{selected_season_text}'), 'q' salir: ")
        if mode == '1': dl_mode = "single"; break
        elif mode == '2': return "season", None
        elif mode.lower() == 'q': return None, None
        else: print("Opción inválida.")

    if dl_mode == "single":
        print(f"\n--- Selección de Episodio (para {selected_season_text}) ---")
        if not current_episode_elements: print("No hay episodios listados."); return None, None
        
        ep_titles = []
        for i, card_el in enumerate(current_episode_elements):
            title = "Desconocido"
            try:
                img = WebDriverWait(card_el, 2).until(EC.presence_of_element_located((By.XPATH, ".//img[@aria-label]")))
                title = img.get_attribute("aria-label").strip()
            except:
                try: h2 = WebDriverWait(card_el, 1).until(EC.presence_of_element_located((By.XPATH, ".//h2"))); title = h2.text.strip()
                except: title = f"Episodio sin título {i+1}"
            ep_titles.append(title); print(f"  {i+1}. {title}")
        
        while True:
            ep_choice = input(f"Elige episodio (1-{len(ep_titles)}), o título/número exacto, 'q' salir: ")
            if ep_choice.lower() == 'q': return None, None
            try:
                idx = int(ep_choice) - 1
                if 0 <= idx < len(ep_titles): return dl_mode, ep_titles[idx] # Devuelve el título exacto
                else: print("Número fuera de rango.")
            except ValueError: return dl_mode, ep_choice # Asumir que es el título/número directo
    return None, None


def main():
    driver = None
    try:
        driver = setup_driver_local()

        all_series_map = get_all_series(driver)
        if not all_series_map: print("No se pudieron obtener series. Abortando."); return
        
        series_slug = prompt_for_series(all_series_map)
        if not series_slug: print("No se seleccionó serie. Abortando."); return
            
        current_series_url = build_series_url_from_slug(series_slug)
        
        selected_season_text = select_season_interactive(driver, current_series_url)
        if not selected_season_text: print("No se seleccionó temporada. Abortando."); return

        # Obtener elementos de episodio DESPUÉS de seleccionar la temporada
        current_episode_elements = get_episode_elements_for_current_season(driver)

        download_mode, target_episode_input = prompt_for_download_mode_and_episode(driver, selected_season_text, current_episode_elements)
        if not download_mode: print("No se seleccionó modo. Abortando."); return
            
        print(f"\n--- Iniciando Descargas ---")
        print(f"Serie: {series_slug}, Temporada: {selected_season_text}, Modo: {download_mode}")

        series_folder = sanitize_filename(series_slug)
        season_folder_match = re.match(r"(Temporada\s*\d+)", selected_season_text)
        season_folder = sanitize_filename(season_folder_match.group(1) if season_folder_match else selected_season_text.split('(')[0].strip())
        season_output_dir = os.path.join(OUTPUT_BASE_DIR, series_folder, season_folder)

        if download_mode == "single":
            if not target_episode_input: print("Error: No episodio para modo single."); return
            
            ep_title_normalized = target_episode_input
            if target_episode_input.isdigit() and EPISODE_NUMBER_PREFIX and not target_episode_input.startswith(EPISODE_NUMBER_PREFIX):
                ep_title_normalized = f"{EPISODE_NUMBER_PREFIX}{target_episode_input}"
            
            print(f"  Buscando tarjeta para episodio: '{ep_title_normalized}'")
            ep_card_xpath = f"//div[contains(@class, 'card--video')][.//img[@aria-label='{ep_title_normalized}']]"
            try:
                ep_card = WebDriverWait(driver, SELENIUM_TIMEOUT).until(EC.presence_of_element_located((By.XPATH, ep_card_xpath)))
                mpd_url = click_episode_and_get_mpd(driver, ep_card, ep_title_normalized)
                if mpd_url:
                    out_path = os.path.join(season_output_dir, f"{sanitize_filename(ep_title_normalized)}.mp4")
                    download_video_with_yt_dlp(mpd_url, out_path, current_series_url)
                else: print(f"  No MPD para '{ep_title_normalized}'.")
            except TimeoutException: print(f"  Timeout: No se encontró tarjeta para '{ep_title_normalized}'.")

        elif download_mode == "season":
            if not current_episode_elements: print(f"No episodios para '{selected_season_text}'."); return
            total_eps = len(current_episode_elements)
            print(f"Descargando {total_eps} episodios de '{selected_season_text}'...")

            for i, ep_card_el in enumerate(current_episode_elements):
                ep_title = "Desconocido"
                try:
                    img = WebDriverWait(ep_card_el, 2).until(EC.presence_of_element_located((By.XPATH, ".//img[@aria-label]")))
                    ep_title = img.get_attribute("aria-label").strip()
                except: 
                    try: h2=WebDriverWait(ep_card_el,1).until(EC.presence_of_element_located((By.XPATH,".//h2")));ep_title=h2.text.strip()
                    except: ep_title = f"episodio_incognito_{i+1}"
                
                print(f"\n--- Procesando {i+1}/{total_eps}: '{ep_title}' ---")
                mpd_url = None
                for attempt in range(MAX_RETRIES_MPD + 1):
                    print(f"  Intento MPD {attempt + 1}/{MAX_RETRIES_MPD + 1}...")
                    mpd_url = click_episode_and_get_mpd(driver, ep_card_el, ep_title)
                    if mpd_url: break
                    if attempt < MAX_RETRIES_MPD: print(f"  Fallo. Reintentando en 5s..."); time.sleep(5)
                
                if mpd_url:
                    out_path = os.path.join(season_output_dir, f"{sanitize_filename(ep_title)}.mp4")
                    download_video_with_yt_dlp(mpd_url, out_path, current_series_url)
                else: print(f"  No MPD para '{ep_title}'. Saltando.")
                time.sleep(3)
    
    except KeyboardInterrupt: print("\nProceso interrumpido por el usuario.")
    except Exception as e:
        print(f"Error CRÍTICO en main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver: print("Cerrando navegador..."); driver.quit()
        print("--- Proceso finalizado ---")

if __name__ == "__main__":
    main()
