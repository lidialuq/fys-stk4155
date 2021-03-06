#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 22 15:33:14 2021
@author: lidia
"""
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils import resample, shuffle
from sklearn import linear_model
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
#np.random.seed(seed=42)


class FrankeFunction():
    '''
    Class to sample franke function
    Args:
        axis_n (int): number of datapoint per axis (total n = axis_n^2)
        noise_var (float or int): variance of the noise
        plot (bool): Plot franke function?
    '''
    def __init__(self, axis_n = 20, noise_var = 0, plot = False):
        # Generate x and y vectors divided equally in a 2d grid
        x = np.linspace(0, 1, axis_n) 
        y = np.linspace(0, 1, axis_n)
        
        self.x_2d, self.y_2d = np.meshgrid(x,y)
        self.x = self.x_2d.ravel()
        self.y = self.y_2d.ravel()
        
        # Generate z, add noise
        z = self.franke_function(self.x, self.y)
        noise = np.random.normal(0,noise_var,(self.x.shape))
        self.z = z + noise
            
        # In order to plot the function, use x_2d and y_2d as input instead
        if plot: 
            z_2d = self.franke_function(self.x_2d, self.y_2d)
            noise = np.random.normal(0,noise_var,(self.x_2d.shape))
            z_2d = z_2d + noise
            self.plot(self.x_2d, self.y_2d, z_2d)
            
    def franke_function(self, x, y):
        '''
        Returns the values of the franke function evaluated at x,y
        The shape of the returned z array is equal to the shape of the x and y 
        inputs.
        '''
        term1 = 0.75*np.exp(-(0.25*(9*x-2)**2) - 0.25*((9*y-2)**2))
        term2 = 0.75*np.exp(-((9*x+1)**2)/49.0 - 0.1*(9*y+1))
        term3 = 0.5*np.exp(-(9*x-7)**2/4.0 - 0.25*((9*y-3)**2))
        term4 = -0.2*np.exp(-(9*x-4)**2 - (9*y-7)**2)
        return term1 + term2 + term3 + term4
        
    def plot(self, x_2d, y_2d, z_2d):

        fig = plt.figure()
        ax = fig.gca(projection='3d')
        surf = ax.plot_surface(x_2d, y_2d, z_2d, cmap=cm.coolwarm,
                       linewidth=0, antialiased=False)
        # Customize the z axis.
        ax.set_zlim(-0.10, 1.40)
        ax.zaxis.set_major_locator(LinearLocator(10))
        ax.zaxis.set_major_formatter(FormatStrFormatter('%.02f'))
        ax.set_title('Original data')

        # Add a color bar which maps values to colors.
        fig.colorbar(surf, shrink=0.5, aspect=5)
        plt.show()
  


class LinearRegression():
    '''
    Methods needed to preform linear regression (OLS, lasso and Ridge) and 
    evaluate the model using bootstrap and k-fold
    Args:
        x (1d array): x-coordinates 
        y (1d array): y-coordinates
        z_data (1d array): z vector created by FrankeFunction()
        degree (int): degree of polynomial to use in regression
        split (bool): split the data in train and test
        test_size (float): amount of data used in test (between 0 and 1)
        model (str): model to use in regression ('OLS', 'Ridge', 'Lasso')
        seed: seed to split the data in order to get reproducable results
        plot (bool): Plot the mode output? (currently not working...)
    '''
    def __init__(self, x, y, z_data, degree = 3, split = False, test_size = 0.3,
                 model = 'OLS', seed = 42, lamb=0,plot = False):
        
        self.degree = degree
        self.x = x
        self.y = y
        self.z_data = z_data
        self.X = self.design_matrix(x, y)
        self.lamb = lamb
        
        if split: 
            
            self.X_train, self.X_test, self.z_train, self.z_test = \
            self.split_and_scale(self.X, self.z_data, test_size) 
            
            if model == 'OLS':
                self.beta = self.OLS(self.X_train, self.z_train)
                self.z_model = self.predict(self.X_test, self.beta)
                self.z_model_train = self.predict(self.X_train, self.beta)
                if plot:
                    x_plot, y_plot = np.linspace(0, 1, 20), np.linspace(0, 1, 20)
                    x_2d_plot, y_2d_plot = np.meshgrid(x_plot,y_plot)
                    x_plot, y_plot = x_2d_plot.ravel(), y_2d_plot.ravel()
                    X_plot = self.design_matrix(x_plot, y_plot)
                    z_plot = self.predict(X_plot, self.beta)
                    self.plot(x_2d_plot, y_2d_plot, z_plot)
            elif model == 'Ridge':
                self.beta = self.Ridge_regression(self.X_train, self.z_train)
                self.z_model = self.predict(self.X_test, self.beta)
                self.z_model_train = self.predict(self.X_train, self.beta)
                if plot:
                    x_plot, y_plot = np.linspace(0, 1, 20), np.linspace(0, 1, 20)
                    x_2d_plot, y_2d_plot = np.meshgrid(x_plot,y_plot)
                    x_plot, y_plot = x_2d_plot.ravel(), y_2d_plot.ravel()
                    X_plot = self.design_matrix(x_plot, y_plot)
                    z_plot = self.predict(X_plot, self.beta)
                    self.plot(x_2d_plot, y_2d_plot, z_plot)
            elif model == 'Lasso':
                self.beta, self.intercept = self.Lasso_regression(self.X_train, self.z_train)
                self.z_model = self.predict(self.X_test, self.beta,self.intercept)
                self.z_model_train = self.predict(self.X_train, self.beta, self.intercept)
                if plot:
                    x_plot, y_plot = np.linspace(0, 1, 20), np.linspace(0, 1, 20)
                    x_2d_plot, y_2d_plot = np.meshgrid(x_plot,y_plot)
                    x_plot, y_plot = x_2d_plot.ravel(), y_2d_plot.ravel()
                    X_plot = self.design_matrix(x_plot, y_plot)
                    z_plot = self.predict(X_plot, self.beta)
                    self.plot(x_2d_plot, y_2d_plot, z_plot)   
        else:
            if model == 'OLS':
                self.beta = self.OLS(self.X, self.z_data)
                self.z_model = self.predict(self.X, self.beta)
            elif model == 'Ridge':
                self.beta = self.Ridge_regression(self.X, self.z_data)
                self.z_model = self.predict(self.X, self.beta)
            elif model == 'Lasso':
                self.beta, self.intercept = self.Lasso_regression(self.X, self.z_data)
                self.z_model = self.predict(self.X, self.beta, intercept=self.intercept)
                
    def split_and_scale(self, X, z, test_size):
        '''
        Split data in train and test, then scale both
        '''
        X_train, X_test, z_train, z_test = \
        train_test_split(self.X, self.z_data, test_size=test_size, 
                         shuffle=True) 
        for i in range(len(X_train.T)):
            X_train[:,i] = X_train[:,i] - np.mean(X_train[:,i])
            X_test[:,i]  = X_test[:,i] - np.mean(X_test[:,i])
        z_train = z_train - np.mean(z_train)
        z_test = z_test - np.mean(z_test)

        return X_train, X_test, z_train, z_test
    
                
    def OLS(self, X, z):
        '''
        Get parameters for ordinary least squares regression
        Args: 
            X (2d array): design matrix
            z (1d array): z vector (input to model)
        Return: 
            beta (1d array): regression parameters
        '''
        beta = np.linalg.pinv(X.T @ X) @ X.T @ z
        return beta
    
    def Ridge_regression(self, X, z):
        '''
        Get parameters for Ridge regression
        Args: 
            X (2d array): design matrix
            z (1d array): z vector (input to model)
        Return: 
            beta (1d array): regression parameters
        '''
        A = self.lamb*np.eye(len(X.T))
        # A[0,0] = 0
        beta = np.linalg.pinv(X.T @ X + A) @  (X.T @ z)
        return beta

    def Lasso_regression(self, X, z):
        '''
        Get parameters for Lasso regression
        Args: 
            X (2d array): design matrix
            z (1d array): z vector (input to model)
            lambd (scalar): lambda value for sparsity constraint parameter
        Return: 
            beta (1d array): regression parameters
        '''

        model = linear_model.Lasso(alpha=self.lamb,max_iter=10000)
        reg = model.fit(X,z)
        beta = reg.coef_
        intercept = reg.intercept_
        return beta.T, intercept
    
        
    def design_matrix(self, x, y):
        '''
        Creates the design matrix
        Args:
            x (1d array): x-coordinates 
            y (1d array): y-coordinates
            degree (int): degree of polynomial in model
        Returns: 
            X (2d array): design matrix
        '''
        X = []
        for y_exp in range(self.degree +1):
            for x_exp in range(self.degree +1):
                if y_exp + x_exp <= self.degree:
                    X.append(x**x_exp * y**y_exp)
        X = (np.array(X).T).squeeze()
        return X

    def predict(self, X, beta,intercept=0):
        '''
        Predicts z values from regression parameters and the design matrix
        Args: 
            X (2d array): design matrix
            beta (1d array): regression parameters
        Return: 
            z (1d array): predicted z-values
        '''
        return (X @ beta)+intercept
        
    def plot(self, x_2d, y_2d, z):
        '''
        Plot a z vector (after reshaping) given a x and y mesh.
        Can be used to plot z_model in order to visualize results
        '''

        # Reshape z vector into 2d matrix to plot
        z_2d = z.reshape(x_2d.shape[1], x_2d.shape[0])

        # Plot
        fig = plt.figure()
        ax = fig.gca(projection='3d')
        surf = ax.plot_surface(x_2d, y_2d, z_2d, cmap=cm.coolwarm,
                               linewidth=0, antialiased=False)
        # Customize the z axis.
        ax.set_zlim(-0.10, 1.40)
        ax.zaxis.set_major_locator(LinearLocator(10))
        ax.zaxis.set_major_formatter(FormatStrFormatter('%.02f'))
        ax.set_title('Model')
        # Add a color bar which maps values to colors.
        fig.colorbar(surf, shrink=0.5, aspect=5)
        plt.show()
    
        
    def MSE(self, z, z_model):
        sum_sq_error = np.sum((z - z_model) ** 2)
        mse = sum_sq_error/len(z_model)
        
        return mse
    
    def R2(self, z_test, z_model):
        sum_sq_error = np.sum((z_test - z_model) ** 2)
        sum_sq_res = np.sum((z_test - np.mean(z_test)) ** 2)
        
        return 1 - (sum_sq_error / sum_sq_res)
    
    def bias(self, z, z_model):
        
        return np.mean((np.mean(z_model) - z)**2)
    
    
    def var(self, z_model):
        
        var_numpy = np.var(z_model)
        var = np.mean((np.mean(z_model)-z_model)**2)
        if var_numpy != var:
            print('Warning: Something is wrong with variance')
        return var
        
    def beta_variance(self, X, sigma_sq = 1):
        return np.diagonal( sigma_sq * (np.linalg.pinv(X.T @ X)))

    
    # TODO MSE train not working, else fine
    def bootstrap(self, X_train, X_test, z_train, z_test, bootstrap_nr=None, model='OLS', lamb=0):
        """
        Bootstrap sampling. 
        Args: 
            X_train (2d array): train design matrix
            X_test (2d array): test design matrix
            z_train (1d array): train z vector
            z_test (1d array): test z vector
            bootstrap_nr: number of bootstraps, defaults to len(z_train)
            model (str): Regression model used. 'OLS', 'Ridge', or 'Lasso' 
            Defaults to OLS. 
            lamb (float): value of lambda for Ridge and Lasso regressions
            
        Returns: 
            error (float): test MSE
            bias (float)
            variance (float)
            error_train (float): tain MSE
        """
        
        if not bootstrap_nr: bootstrap_nr = len(z_train)
        
        z_model = np.empty((len(z_test), bootstrap_nr))
        z_model_train = np.empty((len(z_train), bootstrap_nr))
        z_train_matrix = np.empty((len(z_train), bootstrap_nr))
        z_test_matrix = np.empty((len(z_test), bootstrap_nr))
        
        for i in range(bootstrap_nr):
            
            tmp_X_train, tmp_z_train = resample(X_train, z_train, replace=True)

            if model == "OLS": tmp_beta = self.OLS(tmp_X_train, tmp_z_train)
            if model == "Ridge": tmp_beta = self.Ridge_regression(tmp_X_train, tmp_z_train,lamb)
            if model == "Lasso": tmp_beta = self.Lasso_regression(tmp_X_train, tmp_z_train,lamb)
            
            tmp_z_model = self.predict(X_test, tmp_beta)
            tmp_z_model_train = self.predict(tmp_X_train, tmp_beta)
            z_model[:, i] = tmp_z_model
            z_model_train[:, i] = tmp_z_model_train
            z_train_matrix[:, i] = tmp_z_train
            z_test_matrix[:, i] = z_test
            
        error = np.mean( np.mean((z_test.reshape(-1,1) - z_model)**2, axis=1, keepdims=True) )
        bias = np.mean( (z_test_matrix - np.mean(z_model, axis=1, keepdims=True))**2 )
        variance = np.mean( np.var(z_model, axis=1, keepdims=True) )
        error_train = np.mean( np.mean((z_train_matrix - z_model_train)**2, axis=1, keepdims=True) )

        return error, bias, variance, error_train


    def kfold(self, X, z, k=5, model="OLS", lamb=0):
        """
        Cross-validation 
        Args: 
            X (2d array): design matrix
            z (1d array): z-vector
            k (int): number of folds to divide data into
            model (str): Regression model used. 'OLS', 'Ridge', or 'Lasso' 
            Defaults to OLS. 
            lamb (float): value of lambda for Ridge and Lasso regressions
            
        Returns: 
            z_train (list[1d array]): List of arrays of len(z_train). The list 
                has length = bootstrap_nr
            z_model ((list[1d array]): List of len=bootstrap_nr of arrays of 
                     len(z_train)
            z_model ((list[1d array]): List of len=bootstrap_nr of arrays of 
                     len(z_test)
        """
        
        # shuffle X and z together (so that they still match)
        X, z = shuffle(X, z, random_state=42)
        # split into k vectors
        X_folds = np.array_split(X, k)
        z_folds = np.array_split(z, k)

        MSE_v = []
        MSE_train_v = []        

        for i in range(k):
            # test vectors are fold index i, train vectors the rest
            tmp_X_test = X_folds[i]
            tmp_z_test = z_folds[i]
            tmp_X_train = np.concatenate(X_folds[:i] + X_folds[i+1:])
            tmp_z_train = np.concatenate(z_folds[:i] + z_folds[i+1:])
            
            # regression
            if model == "OLS": tmp_beta = self.OLS(tmp_X_train, tmp_z_train)
            if model == "Ridge": tmp_beta = self.Ridge_regression(tmp_X_train, tmp_z_train,lamb)
            if model == "Lasso": tmp_beta = self.Lasso_regression(tmp_X_train, tmp_z_train,lamb)
            
            # predict
            tmp_z_model = self.predict(tmp_X_test, tmp_beta)
            tmp_z_model_train = self.predict(tmp_X_train, tmp_beta)
            
            MSE_v.append( self.MSE(tmp_z_test, tmp_z_model))
            MSE_train_v.append( self.MSE(tmp_z_train, tmp_z_model_train))            
        
        return np.mean(MSE_v), np.mean(MSE_train_v) 
    

if __name__ == '__main__':
    
    # Get input data, plot function 
    ff = FrankeFunction(noise_var = 0.05, axis_n = 20, plot=True)
    # Linear regression
    ols = LinearRegression(ff.x, ff.y, ff.z, degree = 5, split=True, test_size = 0.3, plot=False)
    #ols.plot(ff.x_2d, ff.y_2d, ols.z_model)
    print(ols.MSE(ols.z_test, ols.z_model))
    
