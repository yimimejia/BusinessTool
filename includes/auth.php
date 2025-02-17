<?php
session_start();

function checkLogin() {
    if (!isset($_SESSION['user_id'])) {
        header('Location: login.php');
        exit();
    }
}

function isAdmin() {
    return isset($_SESSION['es_admin']) && $_SESSION['es_admin'] == 1;
}

function isServicio() {
    return isset($_SESSION['usuario']) && $_SESSION['usuario'] == 'servicio';
}

function getUserId() {
    return $_SESSION['user_id'] ?? null;
}

function getUsername() {
    return $_SESSION['usuario'] ?? null;
}
?>
