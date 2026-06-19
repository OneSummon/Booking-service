template_checkin_reminder_text = """
Напоминание: ваш заезд в отель через 24 часа!

Бронь №{booking_id}
Отель: {hotel_name}
Номер: {room_type_name}
Дата заезда: {check_in}
Дата выезда: {check_out}
Количество гостей: {guests_count}
"""

template_checkin_reminder_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 22px; letter-spacing: 1px; }}
    .header p {{ color: #a0a0b0; margin: 8px 0 0; font-size: 14px; }}
    .badge {{ display: inline-block; background: #f0a500; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-top: 12px; }}
    .body {{ padding: 32px; }}
    .booking-id {{ font-size: 13px; color: #888; margin-bottom: 20px; }}
    .booking-id span {{ font-weight: bold; color: #1a1a2e; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ padding: 10px 0; font-size: 14px; border-bottom: 1px solid #f0f0f0; }}
    td:first-child {{ color: #888; width: 45%; }}
    td:last-child {{ color: #1a1a2e; font-weight: 500; }}
    .footer {{ padding: 20px 32px; text-align: center; font-size: 12px; color: #bbb; border-top: 1px solid #f0f0f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⏰ Заезд через 24 часа!</h1>
      <p>Не забудьте подготовиться к поездке</p>
      <span class="badge">НАПОМИНАНИЕ</span>
    </div>
    <div class="body">
      <div class="booking-id">Бронь <span>№{booking_id}</span></div>
      <table>
        <tr>
          <td>Отель</td>
          <td>{hotel_name}</td>
        </tr>
        <tr>
          <td>Тип номера</td>
          <td>{room_type_name}</td>
        </tr>
        <tr>
          <td>Дата заезда</td>
          <td>{check_in}</td>
        </tr>
        <tr>
          <td>Дата выезда</td>
          <td>{check_out}</td>
        </tr>
        <tr>
          <td>Гостей</td>
          <td>{guests_count}</td>
        </tr>
      </table>
    </div>
    <div class="footer">
      Хорошей поездки!
    </div>
  </div>
</body>
</html>
"""

template_confirmed_booking_text = """
Бронь №{booking_id} подтверждена!
Оплата прошла успешно.

Отель: {hotel_name}
Номер: {room_type_name}
Дата заезда: {check_in}
Дата выезда: {check_out}
Количество гостей: {guests_count}
Количество ночей: {nights_count}
Итоговая цена: {total_price} рублей
"""

template_confirmed_booking_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 22px; letter-spacing: 1px; }}
    .header p {{ color: #a0a0b0; margin: 8px 0 0; font-size: 14px; }}
    .badge {{ display: inline-block; background: #27ae60; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-top: 12px; }}
    .body {{ padding: 32px; }}
    .booking-id {{ font-size: 13px; color: #888; margin-bottom: 20px; }}
    .booking-id span {{ font-weight: bold; color: #1a1a2e; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ padding: 10px 0; font-size: 14px; border-bottom: 1px solid #f0f0f0; }}
    td:first-child {{ color: #888; width: 45%; }}
    td:last-child {{ color: #1a1a2e; font-weight: 500; }}
    .total {{ margin-top: 24px; background: #f8f8f8; border-radius: 8px; padding: 16px 20px; display: flex; justify-content: space-between; }}
    .total-label {{ font-size: 14px; color: #888; }}
    .total-price {{ font-size: 20px; font-weight: bold; color: #1a1a2e; }}
    .footer {{ padding: 20px 32px; text-align: center; font-size: 12px; color: #bbb; border-top: 1px solid #f0f0f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>✅ Бронирование подтверждено</h1>
      <p>Оплата прошла успешно</p>
      <span class="badge">ОПЛАЧЕНО</span>
    </div>
    <div class="body">
      <div class="booking-id">Бронь <span>№{booking_id}</span></div>
      <table>
        <tr>
          <td>Отель</td>
          <td>{hotel_name}</td>
        </tr>
        <tr>
          <td>Тип номера</td>
          <td>{room_type_name}</td>
        </tr>
        <tr>
          <td>Дата заезда</td>
          <td>{check_in}</td>
        </tr>
        <tr>
          <td>Дата выезда</td>
          <td>{check_out}</td>
        </tr>
        <tr>
          <td>Гостей</td>
          <td>{guests_count}</td>
        </tr>
        <tr>
          <td>Ночей</td>
          <td>{nights_count}</td>
        </tr>
      </table>
      <div class="total">
        <span class="total-label">Итоговая цена</span>
        <span class="total-price">{total_price} ₽</span>
      </div>
    </div>
    <div class="footer">
      Ждём вас! Хорошего отдыха.
    </div>
  </div>
</body>
</html>
"""

template_create_booking_text = """
Бронь №{booking_id} создана!
Ожидает оплаты.

Отель: {hotel_name}
Номер: {room_type_name}
Дата заезда: {check_in}
Дата выезда: {check_out}
Количество гостей: {guests_count}
Количество ночей: {nights_count}
Итоговая цена: {total_price} рублей
"""

template_create_booking_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 22px; letter-spacing: 1px; }}
    .header p {{ color: #a0a0b0; margin: 8px 0 0; font-size: 14px; }}
    .badge {{ display: inline-block; background: #f0a500; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-top: 12px; }}
    .body {{ padding: 32px; }}
    .booking-id {{ font-size: 13px; color: #888; margin-bottom: 20px; }}
    .booking-id span {{ font-weight: bold; color: #1a1a2e; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ padding: 10px 0; font-size: 14px; border-bottom: 1px solid #f0f0f0; }}
    td:first-child {{ color: #888; width: 45%; }}
    td:last-child {{ color: #1a1a2e; font-weight: 500; }}
    .total {{ margin-top: 24px; background: #f8f8f8; border-radius: 8px; padding: 16px 20px; display: flex; justify-content: space-between; }}
    .total-label {{ font-size: 14px; color: #888; }}
    .total-price {{ font-size: 20px; font-weight: bold; color: #1a1a2e; }}
    .footer {{ padding: 20px 32px; text-align: center; font-size: 12px; color: #bbb; border-top: 1px solid #f0f0f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🏨 Бронирование создано</h1>
      <p>Ваша бронь ожидает оплаты</p>
      <span class="badge">ОЖИДАЕТ ОПЛАТЫ</span>
    </div>
    <div class="body">
      <div class="booking-id">Бронь <span>№{booking_id}</span></div>
      <table>
        <tr>
          <td>Отель</td>
          <td>{hotel_name}</td>
        </tr>
        <tr>
          <td>Тип номера</td>
          <td>{room_type_name}</td>
        </tr>
        <tr>
          <td>Дата заезда</td>
          <td>{check_in}</td>
        </tr>
        <tr>
          <td>Дата выезда</td>
          <td>{check_out}</td>
        </tr>
        <tr>
          <td>Гостей</td>
          <td>{guests_count}</td>
        </tr>
        <tr>
          <td>Ночей</td>
          <td>{nights_count}</td>
        </tr>
      </table>
      <div class="total">
        <span class="total-label">Итоговая цена</span>
        <span class="total-price">{total_price} ₽</span>
      </div>
    </div>
    <div class="footer">
      Если вы не создавали эту бронь — просто проигнорируйте письмо.
    </div>
  </div>
</body>
</html>
"""