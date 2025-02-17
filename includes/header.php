<?php require_once 'auth.php'; ?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FOTO VIDEO MOJICA - Sistema de Gestión</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <link href="styles.css" rel="stylesheet">
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container">
        <a class="navbar-brand" href="#">FOTO VIDEO MOJICA</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            <?php if(isset($_SESSION['user_id'])): ?>
            <ul class="navbar-nav">
                <?php if(isAdmin()): ?>
                <li class="nav-item">
                    <a class="nav-link" href="admin.php">Panel Admin</a>
                </li>
                <?php endif; ?>
                <li class="nav-item">
                    <a class="nav-link" href="edit.php">Trabajos Pendientes</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="trabajos_listos.php">Trabajos Listos</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="login.php?logout=1">Cerrar Sesión</a>
                </li>
            </ul>
            <?php endif; ?>
        </div>
    </div>
</nav>
<div class="container mt-4">
