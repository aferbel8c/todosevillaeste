finalizar=False
precio=0
cantidad=0
miembro=""

while finalizar==False:
    precio=float(input("Escribe el precio unitario: "))
    if precio<0:
        print("El precio no puede ser negativo")
        continue

    cantidad=int(input("Escribe la cantidad: "))
    if cantidad<=0:
        print("La cantidad no puede ser negativa o cero.")
        continue

    miembro=input("¿Eres miembro? (S/N): ").lower
    if miembro=="s" or miembro=="n":
        break
    else:
        print("Escribe S o N.")
print("bucle finalizado")