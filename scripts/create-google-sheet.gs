/**
 * Google Apps Script: создание Google Таблицы для бота техподдержки (Evgesha_20).
 *
 * Как использовать:
 * 1. Откройте https://script.google.com
 * 2. Новый проект → вставьте этот код в Code.gs
 * 3. Выполните один раз функцию createSupportSheet()
 * 4. В логах (View → Logs) или в диалоге появится ID таблицы и ссылка
 * 5. Скопируйте ID в .env как GOOGLE_SHEET_ID
 *
 * Важно: таблица создаётся в аккаунте Google, под которым вы вошли в script.google.com.
 * Для доступа бота (service account) после создания таблицы откройте её в браузере
 * и дайте доступ на редактирование email из credentials.json (client_email).
 */

/**
 * Название создаваемой таблицы
 */
const SPREADSHEET_TITLE = 'Velvet Mebel — заявки техподдержки';

/**
 * Имя первого листа
 */
const SHEET_NAME = 'Заявки';

/**
 * Заголовки столбцов по ТЗ (раздел 4) и bot/services/sheets.py
 * A: Дата, B: Имя, C: Никнейм/ID, D: Модель, E: Статус сборки, F: Номер телефона
 */
const HEADERS = ['Дата', 'Имя', 'Никнейм/ID', 'Модель', 'Статус сборки', 'Номер телефона'];

/**
 * Создаёт новую Google Таблицу с листом и заголовками для бота.
 * Возвращает объект с id и url созданной таблицы.
 *
 * @returns {Object} { id: string, url: string }
 */
function createSupportSheet() {
  const ss = SpreadsheetApp.create(SPREADSHEET_TITLE);
  const id = ss.getId();
  const url = ss.getUrl();

  // Переименовать первый лист
  const sheet = ss.getSheets()[0];
  sheet.setName(SHEET_NAME);

  // Заголовки в первую строку
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
  sheet.setFrozenRows(1);

  // Опционально: задать ширину столбцов для удобства
  sheet.autoResizeColumns(1, HEADERS.length);

  // Сообщение с результатом (лог всегда; диалог только при запуске из открытой таблицы)
  const message =
    'Таблица создана.\n\nID (в .env как GOOGLE_SHEET_ID):\n' +
    id +
    '\n\nСсылка:\n' +
    url +
    '\n\nНе забудьте выдать доступ на редактирование сервисному аккаунту (client_email из credentials.json).';
  Logger.log(message);
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (e) {
    // getUi() недоступен при запуске из редактора — результат уже в Logger (View → Logs)
  }

  return { id: id, url: url };
}

/**
 * Вариант без диалога — только лог. Удобно при запуске из редактора или триггера.
 */
function createSupportSheetSilent() {
  const result = createSupportSheet();
  Logger.log('Spreadsheet ID: %s', result.id);
  return result.id;
}
