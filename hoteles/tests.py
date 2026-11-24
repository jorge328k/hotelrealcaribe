from django.test import TestCase
from django.contrib.auth.models import User
from .models import Hotel


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