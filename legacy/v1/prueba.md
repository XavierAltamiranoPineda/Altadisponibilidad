==================================================
PRUEBA 1 - NUEVA ESCRITURA EN PRIMARY
==================================================

Volver a TERMINAL 1.

use auditoria_iess_db

Insertar:

db.prueba_ha.insertOne({
    mensaje: "Prueba de replicacion inicial",
    fecha: new Date(),
    origen: "mongo1"
})

Consultar:

db.prueba_ha.find().pretty()


==================================================
PRUEBA 2 - VERIFICAR REPLICACIÓN
==================================================

Ir a TERMINAL 2.

use auditoria_iess_db

Ejecutar:

db.prueba_ha.find().pretty()

Debe aparecer el documento creado desde mongo1.

También ejecutar:

rs.printSecondaryReplicationInfo()

Debe mostrar mongo2 y su retraso de replicación.

Idealmente:

replLag: "0 secs"


==================================================
PRUEBA 3 - SIMULAR CAÍDA DEL PRIMARY
==================================================

IMPORTANTE:
La caída se realiza desde PowerShell, NO desde mongosh.

Abrir/usar una terminal PowerShell y ejecutar:

docker stop ctn-mongo-auditoria-1

Esto simula la caída de mongo1.


==================================================
PRUEBA 4 - COMPROBAR ELECCIÓN AUTOMÁTICA
==================================================

Esperar aproximadamente 10-20 segundos.

En TERMINAL 2 ejecutar:

rs.status()

Ahora debe aparecer:

mongo1:27017 -> NOT REACHABLE / DOWN
mongo2:27018 -> PRIMARY
mongo3:27019 -> ARBITER

También ejecutar:

db.hello()

Debe mostrar:

isWritablePrimary: true
primary: "mongo2:27018"


==================================================
PRUEBA 5 - ESCRITURA DURANTE LA CAÍDA
==================================================

En TERMINAL 2:

use auditoria_iess_db

Ejecutar:

db.prueba_ha.insertOne({
    mensaje: "Escritura durante caída de mongo1",
    fecha: new Date(),
    origen: "mongo2"
})

Consultar:

db.prueba_ha.find().pretty()

La escritura debe realizarse correctamente aunque mongo1 esté detenido.


==================================================
PRUEBA 6 - COMPROBAR QUE mongo2 SIGUE OPERATIVO
==================================================

En TERMINAL 2:

db.hello()

Debe indicar:

isWritablePrimary: true
primary: "mongo2:27018"

Y:

rs.status()

Debe mostrar:

mongo2 -> PRIMARY
mongo3 -> ARBITER
mongo1 -> NOT REACHABLE


==================================================
PRUEBA 7 - RECUPERAR mongo1
==================================================

Salir de mongosh si es necesario:

exit

Desde PowerShell ejecutar:

docker start ctn-mongo-auditoria-1

Esperar unos segundos.

Comprobar:

docker ps

Los tres contenedores deben aparecer como activos.


==================================================
PRUEBA 8 - COMPROBAR RECUPERACIÓN DEL NODO
==================================================

Volver a TERMINAL 2.

Ejecutar:

rs.status()

Es posible que durante unos segundos aparezca:

mongo1 -> SECONDARY

Esto es correcto.

mongo2 debería continuar como:

PRIMARY

Mientras mongo1 se sincroniza.


==================================================
PRUEBA 9 - VERIFICAR SINCRONIZACIÓN
==================================================

En TERMINAL 2:

rs.printSecondaryReplicationInfo()

Debe indicar que mongo1 está sincronizándose y finalmente:

replLag: "0 secs"

También comprobar:

rs.status()


==================================================
PRUEBA 10 - COMPROBAR LOS DATOS RECUPERADOS
==================================================

Entrar a mongo1:

docker exec -it ctn-mongo-auditoria-1 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin

Cambiar de base:

use auditoria_iess_db

Ejecutar:

db.prueba_ha.find().pretty()

Debe aparecer también:

"Escritura durante caída de mongo1"

Esto demuestra que mongo1 recuperó los datos que fueron escritos mientras estaba desconectado.


==================================================
PRUEBA 11 - COMPROBAR EL ESTADO FINAL
==================================================

En cualquiera de los nodos disponibles:

rs.status()

El resultado esperado es:

mongo1 -> SECONDARY
mongo2 -> PRIMARY
mongo3 -> ARBITER

IMPORTANTE:

No es obligatorio que mongo1 vuelva automáticamente a PRIMARY.

Lo importante es demostrar que:

- Mongo2 asumió el PRIMARY.
- Las operaciones continuaron.
- Mongo1 se recuperó.
- Mongo1 volvió al Replica Set.
- Los datos fueron sincronizados.


==================================================
PRUEBA OPCIONAL - COMPROBAR QUE LOS 3 CONTENEDORES ESTÁN ACTIVOS
==================================================

Desde PowerShell:

docker ps

Debe mostrar:

ctn-mongo-auditoria-1
ctn-mongo-auditoria-2
ctn-mongo-auditoria-3

Los tres deben estar Up.