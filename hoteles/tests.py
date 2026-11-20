from django.test import TestCase
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