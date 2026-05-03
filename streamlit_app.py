def identificar_parada(latitude, longitude):
    if latitude is None or longitude is None:
        return "Aguardando dados"

    menor_distancia = float("inf")
    parada_mais_proxima = None

    for parada in PARADAS:
        distancia = calcular_distancia_metros(
            latitude,
            longitude,
            parada["lat"],
            parada["lon"]
        )

        if distancia < menor_distancia:
            menor_distancia = distancia
            parada_mais_proxima = parada

    if parada_mais_proxima is not None and menor_distancia <= RAIO_PARADA_METROS:
        return parada_mais_proxima["nome"]

    return "Em rota"
