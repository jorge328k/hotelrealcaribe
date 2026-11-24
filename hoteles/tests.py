from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import (
    ComprobanteTransferencia,
    Habitacion,
    Hotel,
    Huesped,
    Pago,
    Reserva,
    TipoHabitacion,
)


class HotelModelTest(TestCase):
    def setUp(self):
        Hotel.objects.create(
            nombre="Hotel Real Caribe",
            descripcion="Alojamiento en Riohacha",
            direccion="Calle 12 #7-45",
            municipio="Riohacha",
            telefono="3001234567",
            correo="contacto@realcaribe.com"
        )

    def test_hotel_creacion(self):
        hotel = Hotel.objects.get(nombre="Hotel Real Caribe")
        self.assertEqual(hotel.municipio, "Riohacha")


class RegistrationAndLoginTest(TestCase):
    def test_registration_creates_account_without_email(self):
        response = self.client.post('/registro/', {
            'username': 'cliente_nuevo',
            'email': 'cliente@example.com',
            'password': 'clave-segura-123',
        })

        self.assertRedirects(response, '/login/')
        user = User.objects.get(username='cliente_nuevo')
        self.assertTrue(user.check_password('clave-segura-123'))

    def test_login_accepts_email_for_existing_account(self):
        User.objects.create_user(
            username='cliente_existente',
            email='existente@example.com',
            password='clave-segura-123',
        )

        response = self.client.post('/login/', {
            'username': 'existente@example.com',
            'password': 'clave-segura-123',
        })

        self.assertRedirects(response, '/')
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_registration_rejects_case_insensitive_duplicate_username(self):
        User.objects.create_user(
            username='Cliente',
            email='cliente@example.com',
            password='clave-segura-123',
        )

        response = self.client.post('/registro/', {
            'username': 'cliente',
            'email': 'otro@example.com',
            'password': 'otra-clave-123',
        })

        self.assertRedirects(response, '/registro/')
        self.assertEqual(User.objects.filter(username__iexact='cliente').count(), 1)


class TransferProofWorkflowTest(TestCase):
    def setUp(self):
        hotel = Hotel.objects.create(
            nombre='Hotel de prueba',
            descripcion='Hotel de prueba',
            telefono='3001234567',
            correo='prueba@example.com',
        )
        tipo = TipoHabitacion.objects.create(nombre='Doble', precio_base=100000)
        habitacion = Habitacion.objects.create(
            hotel=hotel,
            numero='101',
            piso=1,
            tipo_habitacion=tipo,
            capacidad=2,
            precio=100000,
        )
        self.cliente = User.objects.create_user(
            username='cliente_transferencia',
            password='clave-segura-123',
        )
        huesped = Huesped.objects.create(
            numero_documento=str(self.cliente.id),
            nombres='Cliente',
            apellidos='Prueba',
            telefono='3001234567',
            correo='cliente@example.com',
        )
        self.reserva = Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=date.today() + timedelta(days=2),
            fecha_salida=date.today() + timedelta(days=3),
            estado='CONFIRMADA',
            metodo_pago='TRANSFERENCIA',
            monto_total=100000,
        )

    def test_upload_waits_for_admin_approval_before_recording_payment(self):
        self.client.force_login(self.cliente)
        response = self.client.get('/mis-reservas/')
        self.assertEqual(response.status_code, 200)

        archivo = SimpleUploadedFile(
            'comprobante.pdf',
            b'%PDF-1.4 prueba',
            content_type='application/pdf',
        )
        response = self.client.post(
            f'/mis-reservas/{self.reserva.id}/comprobante/',
            {'comprobante': archivo},
        )

        self.assertRedirects(response, '/mis-reservas/')
        comprobante = ComprobanteTransferencia.objects.get(reserva=self.reserva)
        self.assertEqual(comprobante.estado, 'PENDIENTE')
        self.assertEqual(comprobante.monto, 30000)
        self.assertFalse(Pago.objects.filter(reserva=self.reserva).exists())
        response = self.client.get('/mis-reservas/')
        self.assertContains(response, 'Comprobante recibido')

        administrador = User.objects.create_user(
            username='admin_transferencia',
            password='clave-segura-123',
            is_staff=True,
        )
        self.client.force_login(administrador)
        response = self.client.post('/administracion/reservas/', {
            'reserva_id': self.reserva.id,
            'comprobante_id': comprobante.id,
            'accion': 'aprobar_comprobante',
        })

        self.assertRedirects(response, '/administracion/reservas/')
        comprobante.refresh_from_db()
        self.assertEqual(comprobante.estado, 'APROBADO')
        pago = Pago.objects.get(reserva=self.reserva)
        self.assertEqual(pago.monto, 30000)
        self.assertEqual(pago.metodo, 'TRANSFERENCIA')

        self.client.force_login(administrador)
        response = self.client.get(f'/administracion/comprobantes/{comprobante.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'%PDF-1.4 prueba')

    def test_card_method_is_saved_and_shown_in_reservation_history(self):
        self.client.force_login(self.cliente)
        response = self.client.post('/reservas/', {
            'habitacion': self.reserva.habitacion_id,
            'fecha_entrada': (date.today() + timedelta(days=5)).isoformat(),
            'fecha_salida': (date.today() + timedelta(days=6)).isoformat(),
            'cantidad_huespedes': 1,
            'metodo_pago': 'TARJETA',
        })

        self.assertRedirects(response, '/mis-reservas/')
        reserva_tarjeta = Reserva.objects.exclude(pk=self.reserva.pk).get()
        self.assertEqual(reserva_tarjeta.metodo_pago, 'TARJETA')
        self.assertFalse(Pago.objects.filter(reserva=reserva_tarjeta).exists())
        response = self.client.get('/mis-reservas/')
        self.assertContains(response, 'Tarjeta (coordinación con el hotel)')

        reserva_tarjeta.estado = 'CONFIRMADA'
        reserva_tarjeta.save(update_fields=['estado'])
        response = self.client.get('/mis-reservas/')
        self.assertContains(response, 'pago con tarjeta en línea no está habilitado')