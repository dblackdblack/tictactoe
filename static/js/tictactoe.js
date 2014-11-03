var ticTacToeApp = angular.module('ticTacToeApp', []);

ticTacToeApp.config(function($interpolateProvider) {
  "use strict";

  $interpolateProvider.startSymbol('{$');
  $interpolateProvider.endSymbol('$}');
});

var ticTacToeCtrl = ticTacToeApp.controller('ticTacToeCtrl', function($scope, $q, $http, $timeout) {
  "use strict";

  var parseResponse = function(respData) {
    $scope.cells = respData.cells;
    $scope.gameStatus = respData.status;
  };

  $scope.getLatestGame = function() {
    $http.get('latest_game').success(parseResponse);
  };

  $scope.cells = [
    [null, null, null],
    [null, null, null],
    [null, null, null]
  ];

  $scope.gameStatus = null;

  $scope.getLatestGame();

  $scope.getClassForCell = function(x, y) {
    var emptyStyle = "fa fa-4x";
    var cellVal = $scope.cells[x][y];

    if(cellVal === null) {
      return emptyStyle;
    } else if(cellVal === 'x') {
      return "fa fa-4x fa-close";
    } else if(cellVal === 'o') {
      return "fa fa-4x fa-circle-o";
    }
  };

  $scope.cellClicked = function(x, y) {
    if($scope.cells[x][y] !== null) { // there is already a move at this location
      return;
    } else if ($scope.gameStatus === 'won' || $scope.gameStatus === 'tie') {
      return;
    }

    $scope.showSpinner = true;
    $http.post('cell_click', angular.toJson({x: x, y: y}))
      .success(parseResponse)
      .error(function(respData) {
        angular.noop();
      }).then(function() {
        $scope.showSpinner = false
      });
  };

  $scope.newGame = function() {
    $http.post('new_game').success(parseResponse);
  }
});